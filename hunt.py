"""
Hunt — proxy discovery + health-check controller with beautiful web UI.
Pure Python, asyncio, in-project data.
"""

import asyncio
import json
import logging
import os
import socket
import struct
import time
import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.yaml"
DATA_DIR = PROJECT_DIR / "data"
HUNT_HTML_PATH = PROJECT_DIR / "hunt.html"

logger = logging.getLogger("setproxy.hunt")

DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
]


def country_flag(code: str) -> str:
    if not code or len(code) != 2:
        return "🏳"
    base = 0x1F1E6 - ord('A')
    return chr(base + ord(code[0])) + chr(base + ord(code[1]))


def country_code_from_name(name: str) -> str:
    mapping = {
        "United States": "US", "United Kingdom": "GB", "Germany": "DE",
        "France": "FR", "Netherlands": "NL", "Japan": "JP", "Canada": "CA",
        "Russia": "RU", "China": "CN", "Brazil": "BR", "Spain": "ES",
        "Italy": "IT", "Poland": "PL", "Ukraine": "UA", "India": "IN",
        "Australia": "AU", "Singapore": "SG", "Korea": "KR", "Mexico": "MX",
        "Sweden": "SE", "Norway": "NO", "Finland": "FI", "Switzerland": "CH",
    }
    return mapping.get(name, "")


@dataclass
class ProxyRating:
    address: str
    country: str = ""
    country_code: str = ""
    protocol: str = "http"
    latency_sum: float = 0.0
    latency_count: int = 0
    checks_total: int = 0
    checks_ok: int = 0
    last_check: float = 0.0
    last_latency: float = 0.0
    last_status: str = "untested"  # ok / failed / untested
    first_seen: float = 0.0
    in_blacklist: bool = False
    blacklist_reason: str = ""

    @property
    def latency_avg(self) -> float:
        return self.latency_sum / self.latency_count if self.latency_count else 0.0

    @property
    def success_rate(self) -> float:
        return self.checks_ok / self.checks_total if self.checks_total else 0.0

    @property
    def score(self) -> float:
        """Rating: high success, low latency, more checks = higher score."""
        if self.checks_total == 0 or self.last_status != "ok":
            return 0.0
        sr = self.success_rate
        if self.latency_count == 0:
            return sr * 50
        lat_score = max(0, 100 - self.latency_avg * 10)
        return sr * 50 + lat_score * 0.5

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "country": self.country,
            "country_code": self.country_code,
            "protocol": self.protocol,
            "latency_avg": round(self.latency_avg, 3),
            "last_latency": round(self.last_latency, 3),
            "checks_total": self.checks_total,
            "checks_ok": self.checks_ok,
            "success_rate": round(self.success_rate, 3),
            "score": round(self.score, 2),
            "last_check": self.last_check,
            "last_status": self.last_status,
            "first_seen": self.first_seen,
            "in_blacklist": self.in_blacklist,
            "blacklist_reason": self.blacklist_reason,
        }


class HuntState:
    PHASE_IDLE = "idle"
    PHASE_DOWNLOAD = "downloading"
    PHASE_VALIDATE = "validating"
    PHASE_HEALTH = "health"
    PHASE_DONE = "done"

    def __init__(self, config: dict):
        self.config = config
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.ratings: dict[str, ProxyRating] = {}
        self.blacklist: dict[str, str] = {}
        self.phase: str = self.PHASE_IDLE
        self.phase_started: float = 0.0
        self.task: Optional[asyncio.Task] = None

        # Hunt progress counters
        self.sources_total: int = 0
        self.sources_done: int = 0
        self.downloaded: int = 0
        self.checked: int = 0
        self.checking_total: int = 0
        self.working: int = 0
        self.failed: int = 0
        self.last_event: str = ""
        self.last_proxy: Optional[str] = None
        self.last_country: str = ""
        self.events: list[dict] = []
        self._event_seq = 0
        self._cond = asyncio.Condition()

        # settings
        cfg = config.get("hunt", {})
        self.parallel = cfg.get("parallel", 30)
        self.timeout = cfg.get("timeout", 8)
        self.us_only = cfg.get("us_only", False)
        self.country_filter = cfg.get("country_filter", "")
        self.health_interval = cfg.get("health_interval", 180)
        self.health_parallel = cfg.get("health_parallel", 20)

        self._load_blacklist()
        self._load_state()
        self._load_working_file()

    @property
    def working_file(self) -> Path:
        return DATA_DIR / "working.txt"

    @property
    def blacklist_file(self) -> Path:
        return DATA_DIR / "blacklist.txt"

    @property
    def state_file(self) -> Path:
        return DATA_DIR / "ratings.json"

    def _emit(self, msg: str, kind: str = "info", **kwargs):
        self._event_seq += 1
        ev = {"seq": self._event_seq, "ts": time.time(), "type": kind, "msg": msg}
        ev.update(kwargs)
        self.events.append(ev)
        if len(self.events) > 500:
            self.events = self.events[-300:]
        self.last_event = msg
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self._notify)
        except Exception:
            pass

    def _notify(self):
        async def go():
            async with self._cond:
                self._cond.notify_all()
        try:
            asyncio.ensure_future(go())
        except Exception:
            pass

    def get_snapshot(self) -> dict:
        alive = [r for r in self.ratings.values()
                 if r.last_status == "ok" and not r.in_blacklist]
        sorted_alive = sorted(alive, key=lambda r: r.score, reverse=True)
        dead = [r for r in self.ratings.values() if r.last_status == "failed"]
        banned = [r for r in self.ratings.values() if r.in_blacklist]

        return {
            "phase": self.phase,
            "phase_started": self.phase_started,
            "running": self.phase not in (self.PHASE_IDLE, self.PHASE_DONE),
            "progress": {
                "sources_total": self.sources_total,
                "sources_done": self.sources_done,
                "downloaded": self.downloaded,
                "checking_total": self.checking_total,
                "checked": self.checked,
                "working": self.working,
                "failed": self.failed,
                "last_proxy": self.last_proxy,
                "last_country": self.last_country,
            },
            "counts": {
                "ratings": len(self.ratings),
                "alive": len(alive),
                "dead": len(dead),
                "blacklist": len(banned) + sum(1 for a in self.blacklist if a not in self.ratings),
            },
            "settings": {
                "parallel": self.parallel,
                "timeout": self.timeout,
                "country_filter": self.country_filter,
            },
            "top_proxies": [r.to_dict() for r in sorted_alive[:30]],
            "blacklist": self._blacklist_view(),
            "last_event": self.last_event,
        }

    def _blacklist_view(self) -> list:
        out = []
        for addr, reason in sorted(self.blacklist.items()):
            r = self.ratings.get(addr)
            out.append({
                "address": addr,
                "reason": reason,
                "country": r.country if r else "",
                "score": r.score if r else 0,
            })
        return out

    def start_hunt(self) -> bool:
        if self.phase not in (self.PHASE_IDLE, self.PHASE_DONE):
            return False
        try:
            loop = asyncio.get_event_loop()
            self.task = loop.create_task(self._hunt_cycle())
            return True
        except RuntimeError:
            return False

    def stop_hunt(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.phase = self.PHASE_IDLE
        self._emit("Hunt stopped by user", "warn")

    async def _hunt_cycle(self):
        try:
            self.phase = self.PHASE_DOWNLOAD
            self.phase_started = time.time()
            self._emit("Hunt started", "phase")

            raw = await self._download_sources()
            self.downloaded = len(raw)
            self._emit(f"Downloaded {len(raw)} unique candidates", "info")

            self.phase = self.PHASE_VALIDATE
            self.phase_started = time.time()
            self.checking_total = len(raw)
            self.checked = 0
            self.working = 0
            self.failed = 0
            self._emit(f"Validating {len(raw)} proxies...", "info")

            await self._validate_all(raw)

            self.phase = self.PHASE_HEALTH
            self.phase_started = time.time()
            self._emit(f"Initial validation done. Starting health-check loop", "info")
            self.phase = self.PHASE_DONE
            self._emit("Hunt cycle complete", "ok")

            # Schedule periodic health-check
            asyncio.create_task(self._health_loop())
        except asyncio.CancelledError:
            self._emit("Hunt cancelled", "warn")
        except Exception as e:
            self._emit(f"Hunt error: {e}", "error")
            self.phase = self.PHASE_DONE
            logger.exception("Hunt failed")

    async def _download_sources(self) -> set:
        sem = asyncio.Semaphore(8)
        self.sources_total = len(DEFAULT_SOURCES)
        self.sources_done = 0
        seen = set()

        async def fetch(url: str):
            async with sem:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "curl", "-sSf", "--max-time", "30", url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    stdout, _ = await proc.communicate()
                    self.sources_done += 1
                    if proc.returncode == 0:
                        text = stdout.decode(errors="replace")
                        import re
                        for m in re.finditer(r'(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})', text):
                            ip, port = m.group(1), int(m.group(2))
                            if 1 <= port <= 65535:
                                seen.add(f"{ip}:{port}")
                except Exception as e:
                    self.sources_done += 1
                    self._emit(f"Source failed: {url.split('/')[-2]}: {e}", "warn")

        tasks = [asyncio.create_task(fetch(u)) for u in DEFAULT_SOURCES]
        await asyncio.gather(*tasks)
        return seen

    async def _validate_all(self, proxies: set):
        sem = asyncio.Semaphore(self.parallel)
        lock = asyncio.Lock()
        ok_count = 0
        fail_count = 0

        async def check_one(addr: str):
            nonlocal ok_count, fail_count
            if addr in self.blacklist:
                async with lock:
                    self.checked += 1
                return
            async with sem:
                start = time.monotonic()
                ok, country = await self._check_proxy(addr)
                latency = time.monotonic() - start
                async with lock:
                    self.checked += 1
                    if ok:
                        ok_count += 1
                        self.working = ok_count
                        self.last_proxy = addr
                        self.last_country = country
                    else:
                        fail_count += 1
                        self.failed = fail_count
                    self._update_rating(addr, ok, country, latency)
                    if self.checked % 25 == 0 or ok:
                        pct = int(100 * self.checked / max(1, self.checking_total))
                        self._emit(
                            f"{pct}% {self.checked}/{self.checking_total} | "
                            f"working: {ok_count} | last: {addr} {country}",
                            "progress"
                        )

        tasks = [asyncio.create_task(check_one(p)) for p in proxies]
        await asyncio.gather(*tasks)
        self._save_state()
        self._save_working_file()

    async def _check_proxy(self, addr: str) -> tuple:
        host, port_str = addr.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return False, ""
        is_socks = port in (1080, 10808, 9050, 4145)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, OSError):
            return False, ""

        country = ""
        country_code = ""

        if is_socks:
            if port == 4145:
                ok = await self._socks4_test(reader, writer)
            else:
                ok = await self._socks5_test(reader, writer)
            if not ok:
                try: writer.close()
                except: pass
                return False, ""
            country = "United States"
            country_code = "US"
        else:
            try:
                req = (
                    f"GET http://ip-api.com/json/{host} HTTP/1.0\r\n"
                    f"Host: ip-api.com\r\n"
                    f"User-Agent: setproxy\r\n"
                    f"Connection: close\r\n"
                    f"\r\n"
                )
                writer.write(req.encode())
                await asyncio.wait_for(writer.drain(), timeout=self.timeout)
                buf = b""
                while True:
                    try:
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
                    except asyncio.TimeoutError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    if buf.count(b"}") >= 1 and len(buf) > 200:
                        break
            except Exception:
                return False, ""
            finally:
                try:
                    writer.close()
                except Exception:
                    pass

            sep = buf.find(b"\r\n\r\n")
            if sep == -1:
                sep = buf.find(b"\n\n")
            if sep == -1:
                return False, ""
            try:
                data = json.loads(buf[sep:].strip())
            except Exception:
                return False, ""
            country = data.get("country", "")
            country_code = data.get("countryCode", "")

        if self.country_filter and country_code != self.country_filter:
            return False, country
        if self.us_only and country != "United States":
            return False, country

        connect_ok = await self._check_proxy_connect(host, port, is_socks)
        if not connect_ok:
            return False, country
        return True, country

    async def _check_proxy_connect(self, host: str, port: int, is_socks: bool = False) -> bool:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=self.timeout)
        except Exception:
            return False
        try:
            if is_socks:
                if port == 4145:
                    ok = await self._socks4_test(r, w)
                else:
                    ok = await self._socks5_test(r, w)
                return ok
            else:
                req = f"CONNECT httpbin.org:443 HTTP/1.1\r\nHost: httpbin.org:443\r\n\r\n"
                w.write(req.encode())
                await asyncio.wait_for(w.drain(), timeout=self.timeout)
                resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=12)
                return b"200" in resp.split(b"\r\n")[0]
        except Exception:
            return False
        finally:
            try:
                w.close()
            except Exception:
                pass

    async def _socks5_test(self, r, w) -> bool:
        try:
            w.write(bytes([5, 1, 0])); await w.drain()
            resp = await asyncio.wait_for(r.readexactly(2), timeout=8)
            if resp[1] != 0:
                return False
            req = bytes([5, 1, 0, 3, 13]) + b"httpbin.org" + b"\x01\xbb"
            w.write(req); await w.drain()
            resp = await asyncio.wait_for(r.readexactly(10), timeout=8)
            return resp[1] == 0
        except Exception:
            return False

    async def _socks4_test(self, r, w) -> bool:
        try:
            req = bytes([4, 1, 0, 80, 0, 0, 0, 1]) + b"\x00" + b"httpbin.org\x00"
            w.write(req); await w.drain()
            resp = await asyncio.wait_for(r.readexactly(8), timeout=8)
            return resp[1] == 0x5A
        except Exception:
            return False

    def _update_rating(self, addr: str, ok: bool, country: str, latency: float):
        r = self.ratings.get(addr)
        if not r:
            r = ProxyRating(
                address=addr,
                country=country,
                country_code=country_code_from_name(country),
                first_seen=time.time(),
            )
            # Guess protocol by port
            try:
                p = int(addr.rsplit(":", 1)[1])
                if p in (1080, 10808, 9050):
                    r.protocol = "socks5"
                elif p == 4145:
                    r.protocol = "socks4"
            except ValueError:
                pass
        r.checks_total += 1
        r.last_check = time.time()
        r.last_latency = latency
        if ok:
            r.checks_ok += 1
            r.latency_sum += latency
            r.latency_count += 1
            r.last_status = "ok"
            if country and not r.country:
                r.country = country
                r.country_code = country_code_from_name(country)
        else:
            r.last_status = "failed"
        self.ratings[addr] = r

    async def _health_loop(self):
        while True:
            await asyncio.sleep(self.health_interval)
            try:
                await self._health_check()
            except Exception as e:
                self._emit(f"Health check error: {e}", "error")

    async def _health_check(self):
        candidates = [r for r in self.ratings.values()
                      if r.last_status == "ok" and not r.in_blacklist]
        if not candidates:
            return
        self.phase = self.PHASE_HEALTH
        self.phase_started = time.time()
        self.checking_total = len(candidates)
        self.checked = 0
        self.working = 0
        self.failed = 0
        self._emit(f"Health-checking {len(candidates)} alive proxies", "info")

        sem = asyncio.Semaphore(self.health_parallel)
        lock = asyncio.Lock()
        ok_count = fail_count = 0

        async def check(r: ProxyRating):
            nonlocal ok_count, fail_count
            async with sem:
                start = time.monotonic()
                ok, country = await self._check_proxy(r.address)
                latency = time.monotonic() - start
                async with lock:
                    self.checked += 1
                    if ok:
                        ok_count += 1
                        self.working = ok_count
                    else:
                        fail_count += 1
                        self.failed = fail_count
                    self._update_rating(r.address, ok, country, latency)

        tasks = [asyncio.create_task(check(r)) for r in candidates]
        await asyncio.gather(*tasks)
        self._save_state()
        self._save_working_file()
        self._emit(f"Health check done: {ok_count} ok, {fail_count} failed", "ok")
        self.phase = self.PHASE_DONE

    def blacklist_add(self, address: str, reason: str = ""):
        if not address:
            return
        self.blacklist[address] = reason or "manual"
        if address in self.ratings:
            self.ratings[address].in_blacklist = True
            self.ratings[address].blacklist_reason = reason or "manual"
        self._save_blacklist()
        self._save_state()
        self._save_working_file()
        self._emit(f"Blacklisted: {address} — {reason or 'manual'}", "warn")

    def blacklist_remove(self, address: str):
        self.blacklist.pop(address, None)
        if address in self.ratings:
            self.ratings[address].in_blacklist = False
            self.ratings[address].blacklist_reason = ""
            self.ratings[address].last_status = "ok"  # optimistic, will be re-checked
        self._save_blacklist()
        self._save_state()
        self._save_working_file()
        self._emit(f"Removed from blacklist: {address}", "info")

    def _load_blacklist(self):
        bf = self.blacklist_file
        if bf.exists():
            try:
                for line in bf.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(maxsplit=1)
                    self.blacklist[parts[0]] = parts[1] if len(parts) > 1 else ""
            except Exception:
                pass

    def _save_blacklist(self):
        with open(self.blacklist_file, "w") as f:
            f.write(f"# setproxy blacklist (operator-curated, NOT dead proxies)\n")
            for addr, reason in sorted(self.blacklist.items()):
                f.write(f"{addr}  {reason}\n")

    def _load_state(self):
        sf = self.state_file
        if not sf.exists():
            return
        try:
            data = json.loads(sf.read_text())
            for d in data:
                r = ProxyRating(
                    address=d["address"],
                    country=d.get("country", ""),
                    country_code=d.get("country_code", ""),
                    protocol=d.get("protocol", "http"),
                    latency_sum=d.get("latency_avg", 0) * d.get("checks_ok", 0),
                    latency_count=d.get("checks_ok", 0),
                    checks_total=d.get("checks_total", 0),
                    checks_ok=d.get("checks_ok", 0),
                    last_check=d.get("last_check", 0),
                    last_status=d.get("last_status", "untested"),
                    first_seen=d.get("first_seen", 0),
                )
                self.ratings[r.address] = r
            logger.info(f"Loaded {len(self.ratings)} ratings from state file")
        except Exception as e:
            logger.warning(f"State load failed: {e}")

    def _save_state(self):
        with open(self.state_file, "w") as f:
            json.dump([r.to_dict() for r in self.ratings.values()], f, indent=2)

    def _load_working_file(self):
        if not self.working_file.exists():
            return
        count = 0
        with open(self.working_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                addr = parts[0]
                country = parts[1] if len(parts) > 1 else ""
                if addr in self.ratings or addr in self.blacklist:
                    continue
                r = ProxyRating(
                    address=addr,
                    country=country,
                    country_code=country_code_from_name(country),
                    first_seen=time.time(),
                    last_check=time.time(),
                    checks_total=1,
                    checks_ok=1,
                    last_status="ok",
                )
                try:
                    lat_str = parts[2] if len(parts) > 2 else "0"
                    r.last_latency = float(lat_str)
                except ValueError:
                    pass
                if addr.rsplit(":", 1)[-1] in ("1080", "10808", "9050"):
                    r.protocol = "socks5"
                elif addr.rsplit(":", 1)[-1] == "4145":
                    r.protocol = "socks4"
                self.ratings[addr] = r
                count += 1
        if count:
            logger.info(f"Loaded {count} proxies from working.txt")

    def _save_working_file(self):
        """Write alive (non-blacklisted) proxies to working.txt, atomic."""
        alive = [r for r in self.ratings.values()
                 if r.last_status == "ok" and not r.in_blacklist]
        alive.sort(key=lambda r: r.score, reverse=True)
        tmp = self.working_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            for r in alive:
                f.write(f"{r.address}  {r.country}  {r.last_latency:.3f}\n")
        tmp.rename(self.working_file)


# ============================================================
# Proxy Runner — local proxy server with upstream selection
# ============================================================

class ProxyRunner:
    def __init__(self, state: "HuntState"):
        self.state = state
        self._server: Optional[asyncio.AbstractServer] = None
        self._task: Optional[asyncio.Task] = None
        self.running = False
        self.port = 17277
        self.active_proxy_addr: Optional[str] = None
        self.direct_mode: bool = False
        self.log: list[dict] = []
        self._failover_idx = 0

    @property
    def selected_proxy(self) -> Optional[ProxyRating]:
        if self.active_proxy_addr and self.active_proxy_addr in self.state.ratings:
            return self.state.ratings[self.active_proxy_addr]
        return None

    def select(self, address: Optional[str]):
        self.active_proxy_addr = address
        if address and address not in self.state.ratings:
            port = 80
            try:
                port_str = address.rsplit(":", 1)[1]
                port = int(port_str)
            except (IndexError, ValueError):
                pass
            protocol = "http"
            if port in (1080, 10808, 9050):
                protocol = "socks5"
            elif port == 4145:
                protocol = "socks4"
            r = ProxyRating(address=address, protocol=protocol,
                            last_status="ok", checks_total=1, checks_ok=1,
                            last_check=time.time(), first_seen=time.time())
            self.state.ratings[address] = r
        if address:
            self.state._emit(f"Proxy upstream selected: {address}", "info")

    async def start(self, port: int):
        if self.running:
            return
        self.port = port
        self.running = True
        self._task = asyncio.create_task(self._run())
        self.state._emit(f"Proxy server starting on {port}...", "info")

    async def stop(self):
        self.running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._task and not self._task.done():
            self._task.cancel()
        self.state._emit("Proxy server stopped", "info")

    async def _run(self):
        try:
            self._server = await asyncio.start_server(
                self._handle, "127.0.0.1", self.port)
            addr = self._server.sockets[0].getsockname()
            self.state._emit(f"Proxy listening on {addr[0]}:{addr[1]}", "ok")
            async with self._server:
                await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.state._emit(f"Proxy server error: {e}", "error")
        finally:
            self.running = False

    async def _handle(self, reader, writer):
        peer = writer.get_extra_info("peername")
        target_host = "?"
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=15)
            if not line:
                writer.close(); return
            parts = line.split()
            if len(parts) < 3:
                writer.close(); return
            method = parts[0].upper()

            if method == b"CONNECT":
                target = parts[1].decode(errors="replace")
                if ":" in target:
                    target_host, port_str = target.rsplit(":", 1)
                else:
                    target_host, port_str = target, "443"
                try:
                    target_port = int(port_str)
                except ValueError:
                    target_port = 443

                while True:
                    try:
                        hdr = await asyncio.wait_for(reader.readline(), timeout=15)
                    except Exception:
                        break
                    if hdr in (b"\r\n", b"\n", b""):
                        break

                upstream = await self._connect_upstream(target_host, target_port)
                if not upstream:
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    await writer.drain()
                    writer.close()
                    self._log(peer, target_host, "502 no upstream")
                    return

                up_r, up_w = upstream
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                await self._relay(reader, up_w, up_r, writer)
                self._log(peer, target_host, "ok")
            else:
                await self._handle_http_forward(reader, writer, method, parts[1], peer)
        except Exception as e:
            self._log(peer, target_host, f"err: {e}")
        finally:
            try: writer.close()
            except: pass

    async def _handle_http_forward(self, reader, writer, method, url, peer):
        target = url.decode(errors="replace")
        target_host = ""
        target_port = 80
        raw_headers = []
        if target.startswith("/"):
            host_hdr = None
            while True:
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=15)
                except Exception:
                    break
                if line in (b"\r\n", b"\n", b""): break
                raw_headers.append(line)
                if line.lower().startswith(b"host:"):
                    host_hdr = line[5:].strip().decode(errors="replace")
            if host_hdr and ":" in host_hdr:
                target_host, ps = host_hdr.rsplit(":", 1)
                try: target_port = int(ps)
                except: pass
            elif host_hdr:
                target_host = host_hdr
        else:
            parsed = urlparse(target)
            target_host = parsed.hostname or ""
            target_port = parsed.port or 80

        if not target_host:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n"); await writer.drain(); return

        upstream = await self._connect_upstream(target_host, target_port)
        if not upstream:
            writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n"); await writer.drain()
            self._log(peer, target_host, "502 no upstream"); return

        up_r, up_w = upstream

        if self.direct_mode and not target.startswith("/"):
            parsed = urlparse(target)
            rel_path = parsed.path or "/"
            if parsed.query:
                rel_path += "?" + parsed.query
            up_w.write(method + b" " + rel_path.encode() + b" HTTP/1.1\r\n")
        else:
            up_w.write(method + b" " + url + b" HTTP/1.1\r\n")
        for h in raw_headers:
            up_w.write(h)
        up_w.write(b"\r\n")
        await up_w.drain()

        resp_line = await asyncio.wait_for(up_r.readline(), timeout=30)
        writer.write(resp_line)
        while True:
            try:
                line = await asyncio.wait_for(up_r.readline(), timeout=30)
            except Exception:
                break
            if line in (b"\r\n", b"\n", b""):
                writer.write(b"\r\n"); break
            writer.write(line)
        await writer.drain()
        await self._relay(up_r, writer, reader, up_w)
        self._log(peer, target_host, "ok")

    async def _connect_upstream(self, host: str, port: int):
        if self.direct_mode:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=15)
                self._log(None, f"direct connect ok", f"{host}:{port}")
                return reader, writer
            except Exception as e:
                self._log(None, f"direct connect fail", str(e)[:40])
                return None

        if self.active_proxy_addr:
            r = self.state.ratings.get(self.active_proxy_addr)
            if not r or r.in_blacklist:
                self._log(None, f"selected proxy {self.active_proxy_addr} not available", "")
                r = None
        else:
            r = None

        pool = [r for r in self.state.ratings.values()
                if r.last_status == "ok" and not r.in_blacklist]
        if not pool:
            return None
        pool.sort(key=lambda r: r.score, reverse=True)

        if r and r in pool:
            pool.remove(r)
            pool.insert(0, r)

        for attempt in range(min(len(pool), 8)):
            p = pool[attempt]

            phost, pport_str = p.address.rsplit(":", 1)
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str)), timeout=10)
            except Exception as e:
                self._log(None, f"upstream {p.address} connect fail", str(e)[:40])
                continue

            ok = False
            if p.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
            elif p.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
            else:
                ok = await self._http_connect_cmd(reader, writer, host, port)

            if not ok:
                self._log(None, f"upstream {p.address} CONNECT fail", f"{host}:{port}")
                try: writer.close()
                except: pass
                continue

            self._failover_idx = (attempt + 1) % len(pool)
            return reader, writer

        self._log(None, "502: no working upstream", f"{host}:{port}")
        return None

    async def _http_connect_cmd(self, r, w, h, p):
        req = f"CONNECT {h}:{p} HTTP/1.1\r\nHost: {h}:{p}\r\n\r\n"
        w.write(req.encode()); await w.drain()
        try:
            resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
            status_line = resp.split(b"\r\n")[0]
            self._log(None, f"CONNECT response", status_line.decode(errors="replace"))
            return b"200" in status_line
        except asyncio.TimeoutError:
            self._log(None, f"CONNECT timeout (15s)", f"{h}:{p}")
            return False
        except Exception as e:
            self._log(None, f"CONNECT error", str(e)[:60])
            return False

    async def _socks5_cmd(self, r, w, h, p):
        try:
            w.write(bytes([5, 1, 0])); await w.drain()
            resp = await asyncio.wait_for(r.readexactly(2), timeout=8)
            if resp[1] != 0: return False
            is_ip = all(c.isdigit() or c == "." for c in h)
            if is_ip:
                req = bytes([5, 1, 0, 1]) + socket.inet_aton(h)
            else:
                raw = h.encode()
                req = bytes([5, 1, 0, 3, len(raw)]) + raw
            req += struct.pack(">H", p)
            w.write(req); await w.drain()
            resp = await asyncio.wait_for(r.readexactly(10), timeout=8)
            return resp[1] == 0
        except Exception:
            return False

    async def _socks4_cmd(self, r, w, h, p):
        try:
            req = struct.pack(">BBH", 4, 1, p) + bytes([0, 0, 0, 1]) + b"\x00"
            req += h.encode() + b"\x00"
            w.write(req); await w.drain()
            resp = await asyncio.wait_for(r.readexactly(8), timeout=8)
            return resp[0] == 0 and resp[1] == 0x5A
        except Exception:
            return False

    async def _relay(self, r1, w1, r2, w2):
        first_c2u = True
        first_u2c = True
        async def pipe(r, w, label):
            nonlocal first_c2u, first_u2c
            try:
                while True:
                    data = await r.read(65536)
                    if not data: break
                    if label == "c2u" and first_c2u:
                        first_c2u = False
                        self._log(None, f"relay c2u first len={len(data)} hex={data[:30].hex()}", "")
                    if label == "u2c" and first_u2c:
                        first_u2c = False
                        self._log(None, f"relay u2c first len={len(data)} hex={data[:30].hex()}", "")
                    w.write(data); await w.drain()
            except: pass
            finally:
                try: w.close()
                except: pass
        await asyncio.gather(pipe(r1, w1, "c2u"), pipe(r2, w2, "u2c"))

    def _log(self, peer, target, status):
        entry = {"ts": time.time(), "client": f"{peer[0]}:{peer[1]}" if peer else "?", "target": target, "status": status}
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-150:]

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "port": self.port,
            "active_proxy": self.selected_proxy.to_dict() if self.selected_proxy else None,
            "direct_mode": self.direct_mode,
            "connections": len(self.log),
            "log": list(reversed(self.log[-50:])),
        }


# ============================================================
# Web server
# ============================================================

WEB_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>setproxy</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#222;padding:0;max-width:1400px;margin:0 auto}
h1{font-size:18px;padding:14px 20px 0}
.sub{color:#888;font-size:12px;padding:0 20px 10px}

.tabs{display:flex;gap:0;border-bottom:2px solid #d0d7de;padding:0 20px;margin-bottom:14px}
.tab{padding:8px 16px;cursor:pointer;color:#656d76;font-weight:500;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .1s}
.tab:hover{color:#222}
.tab.active{color:#0969da;border-bottom-color:#0969da}

.tab-content{display:none;padding:0 20px 20px}
.tab-content.active{display:block}

.row{display:flex;gap:14px;flex-wrap:wrap}
.col{flex:1;min-width:280px}
.card{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:14px;margin-bottom:12px}
.card h2{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;font-weight:600}
.metric{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.metric .v{font-size:22px;font-weight:700}
.metric .l{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:.5px}
.ok{color:#1a7f37} .warn{color:#9a6700} .err{color:#cf222e} .bl{color:#8250df} .run{color:#0969da}

button{font:inherit;cursor:pointer;padding:7px 14px;border:1px solid #d0d7de;border-radius:5px;background:#fff;color:#222}
button:hover{background:#e8eaed}
button:disabled{opacity:.4;cursor:default}
button.primary{background:#0969da;border-color:#0969da;color:#fff;font-weight:600;padding:8px 18px}
button.primary:hover{background:#0550ae}
button.primary.green{background:#1a7f37;border-color:#1a7f37}
button.primary.green:hover{background:#14632a}
button.danger{color:#cf222e;border-color:#cf222e}
button.danger:hover{background:#fff0f0}
.btnbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.phase{display:inline-block;padding:3px 8px;border-radius:10px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.phase-idle{background:#e8eaed;color:#656d76}
.phase-downloading{background:#ddf4ff;color:#0969da}
.phase-validating{background:#f4e8ff;color:#8250df}
.phase-health{background:#dafbe1;color:#1a7f37}
.phase-done{background:#dafbe1;color:#1a7f37}
.bar{height:8px;background:#e8eaed;border-radius:4px;overflow:hidden;margin:8px 0}
.bar .fill{height:100%;background:linear-gradient(90deg,#0969da,#8250df);transition:width .4s}
.last-proxy{font:12px/1.4 Menlo,Consolas,monospace;color:#1a7f37;margin-top:6px;display:flex;align-items:center;gap:6px}
.flag{font-size:16px}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #d0d7de}
th{color:#656d76;font-weight:500;font-size:10px;text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0;background:#f6f8fa}
tbody tr:hover{background:#eef1f5}
.tbl-wrap{max-height:400px;overflow-y:auto;border-radius:6px}
.addr{font-family:Menlo,Consolas,monospace;color:#0969da}
.live{font:11px/1.4 Menlo,Consolas,monospace;max-height:200px;overflow-y:auto;background:#f6f8fa;border:1px solid #d0d7de;border-radius:5px;padding:6px}
.live div{padding:1px 0}
.live-ts{color:#888;margin-right:6px}
input[type=text],input[type=number]{border:1px solid #d0d7de;padding:5px 8px;border-radius:4px;font:13px inherit;width:100%}
input[type=text]:focus,input[type=number]:focus{outline:none;border-color:#0969da;box-shadow:0 0 0 2px #b6d4fe}
.bl-form{display:flex;gap:6px;margin-bottom:8px}
.empty{color:#888;font-style:italic;padding:14px;text-align:center}
.empty.small{padding:6px;font-size:11px}
.score-bar{display:inline-block;width:50px;height:5px;background:#e8eaed;border-radius:3px;vertical-align:middle;overflow:hidden}
.score-bar .s{height:100%;background:linear-gradient(90deg,#0969da,#8250df)}
.pulse{display:inline-block;width:8px;height:8px;border-radius:50%;background:#1a7f37;box-shadow:0 0 0 0 rgba(26,127,55,.5);animation:pulse 1.5s infinite;vertical-align:middle}
.pulse.off{background:#bbb;animation:none;box-shadow:none}
.pulse.run{background:#0969da;box-shadow:0 0 0 0 rgba(9,105,218,.5)}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(26,127,55,.4)}70%{box-shadow:0 0 0 8px rgba(26,127,55,0)}100%{box-shadow:0 0 0 0 rgba(26,127,55,0)}}
.status-bar{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:6px;margin-bottom:10px;font-size:13px;font-weight:500}
.status-bar.on{background:#dafbe1;border:1px solid #b2dfbe;color:#1a7f37}
.status-bar.off{background:#f6f8fa;border:1px solid #d0d7de;color:#656d76}
.port-input{display:flex;align-items:center;gap:6px}
.port-input input{width:80px}
.sel-proxy{padding:0}
.sel-addr{font:16px/1.3 Menlo,Consolas,monospace;font-weight:700;color:#0969da;margin-bottom:8px;word-break:break-all}
.sel-badges{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.sel-badge{display:inline-block;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600}
.sel-country{background:#ddf4ff;color:#0969da}
.sel-proto{background:#f4e8ff;color:#8250df}
.sel-stats{display:flex;gap:24px;flex-wrap:wrap}
</style>
</head>
<body>

<h1>setproxy</h1>
<div class="sub">
  <span class="pulse off" id="live-dot" style="margin-right:8px"></span>
  <span id="last-event">ready</span>
</div>

<div class="tabs">
  <div class="tab active" data-tab="hunt" onclick="switchTab('hunt')">Hunt</div>
  <div class="tab" data-tab="proxy" onclick="switchTab('proxy')">Proxy</div>
</div>

<!-- ========= TAB: HUNT ========= -->
<div class="tab-content active" id="tab-hunt">
<div class="row">
<div class="col" style="min-width:320px">

 <div class="card">
<h2>control</h2>
<div class="btnbar" style="margin-bottom:10px">
<button class="primary" id="btn-start" onclick="huntStart()">&#9654; Start Hunt</button>
<button class="danger" id="btn-stop" onclick="huntStop()" disabled>&#9632; Stop</button>
</div>
<div class="btnbar" style="margin-bottom:10px;font-size:12px;color:#656d76">
<span>Country:</span>
<select id="country-filter" onchange="setCountry(this.value)" style="font:inherit;padding:3px 6px;border:1px solid #d0d7de;border-radius:4px;background:#fff">
<option value="">ALL</option>
<option value="US">US</option>
<option value="RU">RU</option>
<option value="GB">GB</option>
<option value="DE">DE</option>
<option value="FR">FR</option>
<option value="NL">NL</option>
<option value="CA">CA</option>
<option value="JP">JP</option>
<option value="BR">BR</option>
<option value="IN">IN</option>
<option value="UA">UA</option>
<option value="PL">PL</option>
</select>
</div>
<div style="margin-top:12px">
<div class="metric"><div class="v ok" id="m-alive">0</div><div class="l">alive</div></div>
<div class="metric"><div class="v warn" id="m-dead">0</div><div class="l">dead</div></div>
<div class="metric"><div class="v bl" id="m-bl">0</div><div class="l">blacklist</div></div>
<div class="metric"><div class="v" id="m-total">0</div><div class="l">rated</div></div>
</div>
</div>

<div class="card">
<h2>progress</h2>
<div class="metric"><div class="v" id="p-pct" style="min-width:50px">0%</div><div class="l" id="p-detail">idle</div></div>
<div class="bar"><div class="fill" id="p-bar"></div></div>
<div style="display:flex;justify-content:space-between;font-size:12px;color:#656d76;margin-top:6px">
<span>checked: <b id="p-checked">0</b> / <b id="p-total">0</b></span>
<span>working: <b class="ok" id="p-working">0</b></span>
</div>
<div class="last-proxy" id="last-proxy" style="visibility:hidden">
<span class="flag" id="last-flag">&#x1F3F3;</span>
<span id="last-addr">&mdash;</span>
<span style="color:#656d76;font-size:11px" id="last-country-name"></span>
</div>
</div>

<div class="card">
<h2>log</h2>
<div class="live" id="hunt-log"></div>
</div>
</div>

<div class="col" style="min-width:480px">

<div class="card">
<h2>top rated alive</h2>
<div class="tbl-wrap">
<table>
<thead><tr>
<th>#</th><th>proxy</th><th>country</th><th>latency</th><th>success</th><th>checks</th><th>score</th><th></th>
</tr></thead>
<tbody id="top-body"></tbody>
</table>
</div>
</div>

<div class="card">
<h2>blacklist</h2>
<div class="bl-form">
<input type="text" id="bl-input" placeholder="ip:port">
<input type="text" id="bl-reason" placeholder="reason">
<button onclick="blAdd()">+</button>
</div>
<div class="tbl-wrap" style="max-height:200px">
<table>
<thead><tr><th>proxy</th><th>reason</th><th>country</th><th></th></tr></thead>
<tbody id="bl-body"></tbody>
</table>
</div>
</div>

</div>
</div>
</div>

 <!-- ========= TAB: PROXY ========= -->
<div class="tab-content" id="tab-proxy">
<div class="row">
<div class="col" style="min-width:320px">

 <div class="card">
<h2>proxy server</h2>
<div class="status-bar off" id="proxy-status-bar">
  <span class="pulse off" id="proxy-dot"></span>
  <span id="proxy-status-text">stopped</span>
</div>
<div class="port-input" style="margin-bottom:10px">
  <span>Port:</span>
  <input type="number" id="proxy-port" value="17277" min="1024" max="65535">
  <button class="primary green" id="btn-proxy-start" onclick="proxyStart()">&#9654; Start</button>
  <button class="danger" id="btn-proxy-stop" onclick="proxyStop()" disabled>&#9632; Stop</button>
</div>
<div style="margin:6px 0;display:flex;align-items:center;gap:8px">
  <label style="display:flex;align-items:center;gap:4px;cursor:pointer;font-size:13px">
    <input type="checkbox" id="direct-toggle" onchange="toggleDirect(this.checked)">
    <b>direct mode</b> (no upstream)
  </label>
</div>
<div class="metric"><div class="v run" id="proxy-connections">0</div><div class="l">connections</div></div>
</div>

<div class="card" id="selected-card" style="display:none">
<h2>selected upstream &#x2191;</h2>
<div class="sel-proxy" id="sel-proxy">
  <div class="sel-addr" id="sel-addr"></div>
  <div class="sel-badges" id="sel-badges"></div>
  <div class="sel-stats" id="sel-stats">
    <div class="metric"><div class="v" id="sel-score">-</div><div class="l">score</div></div>
    <div class="metric"><div class="v" id="sel-lat">-</div><div class="l">latency</div></div>
    <div class="metric"><div class="v" id="sel-sr">-</div><div class="l">success rate</div></div>
    <div class="metric"><div class="v" id="sel-checks">-</div><div class="l">checks</div></div>
  </div>
  <button onclick="proxySelect('')" style="margin-top:6px;font-size:11px">clear selection</button>
</div>
</div>

<div class="card">
<h2>client log</h2>
<div class="live" id="proxy-log" style="max-height:200px"><div class="empty small">proxy not started</div></div>
</div>
</div>

<div class="col" style="min-width:480px">

<div class="card">
<h2>select upstream proxy</h2>
<div class="tbl-wrap" style="max-height:500px">
<table>
<thead><tr>
<th>#</th><th>proxy</th><th>country</th><th>latency</th><th>success</th><th>score</th><th></th>
</tr></thead>
<tbody id="proxy-list-body"></tbody>
</table>
</div>
</div>

</div>
</div>
</div>

<script>
let lastEventSeq=0, huntLogLines=[], proxyLogLines=[];

function flag(c){if(!c||c.length!==2)return'\u{1F3F3}';var b=0x1F1E6-'A'.charCodeAt(0);return String.fromCodePoint(b+c.charCodeAt(0),b+c.charCodeAt(1))}
function fmtTime(t){return new Date(t*1e3).toLocaleTimeString()}

async function api(p,m,g){var o={method:m||'GET',headers:{}};if(g){o.headers['Content-Type']='application/json';o.body=JSON.stringify(g)}return(await fetch(p,o)).json()}

function switchTab(name){document.querySelectorAll('.tab,.tab-content').forEach(function(e){e.classList.toggle('active',e.dataset.tab===name||e.id==='tab-'+name)})}

// ---- HUNT ----
async function huntStart(){var r=await api('/api/hunt/start','POST');if(r.error)alert(r.error)}
async function huntStop(){await api('/api/hunt/stop','POST')}

async function blAdd(){var a=document.getElementById('bl-input').value.trim(),r=document.getElementById('bl-reason').value.trim();if(!a)return;await api('/api/blacklist/add','POST',{address:a,reason:r});document.getElementById('bl-input').value='';document.getElementById('bl-reason').value=''}
async function blRemove(a){await api('/api/blacklist/remove','POST',{address:a})}

// ---- PROXY ----
async function proxyStart(){var p=document.getElementById('proxy-port').value;var s=await api('/api/proxy/start?port='+p,'POST');renderProxy(s)}
async function proxyStop(){var s=await api('/api/proxy/stop','POST');renderProxy(s)}

var _selectedAddr=null;
function renderSelected(ap){
  var card=document.getElementById('selected-card');
  if(!ap){card.style.display='none';_selectedAddr=null;return}
  card.style.display='block';_selectedAddr=ap.address;
  document.getElementById('sel-addr').textContent=ap.address;
  var badges='<span class="sel-badge sel-country">'+flag(ap.country_code)+' '+ap.country+'</span><span class="sel-badge sel-proto">'+ap.protocol+'</span>';
  document.getElementById('sel-badges').innerHTML=badges;
  document.getElementById('sel-score').textContent=ap.score.toFixed(0);
  document.getElementById('sel-lat').textContent=(ap.last_latency||0).toFixed(2)+'s';
  document.getElementById('sel-sr').textContent=(ap.success_rate*100).toFixed(0)+'%';
  document.getElementById('sel-checks').textContent=ap.checks_ok+'/'+ap.checks_total;
}

async function proxySelect(a){
  await api('/api/proxy/select?address='+encodeURIComponent(a||''),'POST');
  if(!a){document.getElementById('selected-card').style.display='none';_selectedAddr=null}
  else{var ps=await api('/api/proxy/status');renderSelected(ps.active_proxy)}
}

function toggleDirect(on){fetch('/api/proxy/direct?on='+(on?'true':'false'),{method:'POST'})}

function renderProxy(s){
var bar=document.getElementById('proxy-status-bar'),dot=document.getElementById('proxy-dot'),txt=document.getElementById('proxy-status-text');
if(s.running){bar.className='status-bar on';dot.className='pulse run';txt.textContent='running on :'+s.port}
else{bar.className='status-bar off';dot.className='pulse off';txt.textContent='stopped'}
document.getElementById('proxy-connections').textContent=s.connections||0;
document.getElementById('btn-proxy-start').disabled=s.running;
document.getElementById('btn-proxy-stop').disabled=!s.running;
document.getElementById('direct-toggle').checked=!!s.direct_mode;
if(s.direct_mode){document.getElementById('selected-card').style.display='none';_selectedAddr=null}
else if(s.active_proxy && s.active_proxy.address!==_selectedAddr) renderSelected(s.active_proxy);
if(!s.direct_mode && !s.active_proxy && _selectedAddr){document.getElementById('selected-card').style.display='none';_selectedAddr=null}

var pl=document.getElementById('proxy-log');
if(s.log && s.log.length){
proxyLogLines=s.log.map(function(e){return '<span class="live-ts">'+fmtTime(e.ts)+'</span> '+e.client+' \u2192 '+e.target+' ['+e.status+']'});
pl.innerHTML=proxyLogLines.join('<br>');
} else if(!s.running) {pl.innerHTML='<div class="empty small">proxy not started</div>'}
}

function renderHunt(s){
['m-alive','m-dead','m-bl','m-total'].forEach(function(k,i){document.getElementById(k).textContent=[s.counts.alive,s.counts.dead,s.counts.blacklist,s.counts.ratings][i]});
var b=document.getElementById('phase-badge');if(b){b.textContent=s.phase;b.className='phase phase-'+s.phase}
document.getElementById('last-event').textContent=s.last_event||'\u2014';
document.getElementById('live-dot').className=s.running?'pulse':'pulse off';
document.getElementById('btn-start').disabled=s.running;
document.getElementById('btn-stop').disabled=!s.running;
var p=s.progress,t=p.checking_total||p.downloaded,c=p.checked,x=t>0?Math.round(100*c/t):0;
document.getElementById('p-pct').textContent=x+'%';
document.getElementById('p-checked').textContent=c;
document.getElementById('p-total').textContent=t;
document.getElementById('p-working').textContent=p.working;
document.getElementById('p-bar').style.width=x+'%';
document.getElementById('p-detail').textContent=s.phase;
var lp=document.getElementById('last-proxy');
if(p.last_proxy){lp.style.visibility='visible';document.getElementById('last-addr').textContent=p.last_proxy;var found=s.top_proxies.find(function(x){return x.address===p.last_proxy});document.getElementById('last-flag').textContent=flag(found?found.country_code:'');document.getElementById('last-country-name').textContent=p.last_country}

// top table
var tb=document.getElementById('top-body');
tb.innerHTML=s.top_proxies.length?s.top_proxies.map(function(p,i){var sc=Math.min(100,Math.max(0,p.score));return'<tr><td style="color:#656d76">'+(i+1)+'</td><td class="addr">'+p.address+'</td><td>'+flag(p.country_code)+' '+p.country+'</td><td>'+p.last_latency.toFixed(2)+'s</td><td>'+(p.success_rate*100).toFixed(0)+'%</td><td>'+p.checks_ok+'/'+p.checks_total+'</td><td><div class="score-bar"><div class="s" style="width:'+sc+'%"></div></div></td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+p.address+'\')">bl</button></td></tr>'}).join(''):'<tr><td colspan="8" class="empty">no alive proxies</td></tr>';

// blacklist
var bb=document.getElementById('bl-body');
bb.innerHTML=s.blacklist.length?s.blacklist.map(function(b){return'<tr><td class="addr">'+b.address+'</td><td style="color:#8250df">'+(b.reason||'\u2014')+'</td><td>'+(b.country||'\u2014')+'</td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+b.address+'\')">\u00d7</button></td></tr>'}).join(''):'<tr><td colspan="4" class="empty">no entries</td></tr>';
}

function renderProxyList(alive){
var tb=document.getElementById('proxy-list-body');
tb.innerHTML=alive.length?alive.map(function(p,i){var sc=Math.min(100,Math.max(0,p.score));return'<tr><td style="color:#656d76">'+(i+1)+'</td><td class="addr">'+p.address+'</td><td>'+flag(p.country_code)+' '+p.country+'</td><td>'+p.last_latency.toFixed(2)+'s</td><td>'+(p.success_rate*100).toFixed(0)+'%</td><td><div class="score-bar"><div class="s" style="width:'+sc+'%"></div></div></td><td><button style="padding:3px 8px;font-size:11px" onclick="proxySelect(\''+p.address+'\')">select</button></td></tr>'}).join(''):'<tr><td colspan="7" class="empty">no proxies available</td></tr>';
}

function renderLog(ev){
ev.forEach(function(e){lastEventSeq=Math.max(lastEventSeq,e.seq);huntLogLines.unshift('<span class="live-ts">'+fmtTime(e.ts)+'</span> '+e.msg);if(huntLogLines.length>200)huntLogLines.length=200});
document.getElementById('hunt-log').innerHTML=huntLogLines.map(function(l){return'<div>'+l+'</div>'}).join('')}

async function poll(){
try{var s=await api('/api/snapshot');renderHunt(s)}catch(e){}
try{var alive=await api('/api/proxy/alive');renderProxyList(alive)}catch(e){}
try{var ps=await api('/api/proxy/status');renderProxy(ps)}catch(e){}
try{var ev=await api('/api/events?since='+lastEventSeq);if(ev.length)renderLog(ev)}catch(e){}}

poll();setInterval(poll,600);
</script>
</body>
</html>"""


def _qs(path: str) -> dict:
    params = {}
    if "?" in path:
        for p in path.split("?", 1)[1].split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = unquote(v)
    return params


class HuntServer:
    def __init__(self, state: HuntState, host: str, port: int):
        self.state = state
        self.host = host
        self.port = port
        self.proxy = ProxyRunner(state)
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle, self.host, self.port)
        addr = self._server.sockets[0].getsockname()
        logger.info(f"Hunt web UI: http://{addr[0]}:{addr[1]}/")
        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=10)
        except Exception:
            writer.close(); return
        if not line:
            writer.close(); return
        try:
            parts = line.split()
            if len(parts) < 2:
                writer.close(); return
            method = parts[0].decode().upper()
            path = parts[1].decode()
        except Exception:
            writer.close(); return

        headers = {}
        while True:
            try:
                hl = await asyncio.wait_for(reader.readline(), timeout=5)
            except Exception:
                break
            if hl in (b"\r\n", b"\n", b""):
                break
            if b":" in hl:
                k, v = hl.decode(errors="replace").split(":", 1)
                headers[k.strip().lower()] = v.strip()

        cl = int(headers.get("content-length", 0))
        body = b""
        if cl > 0:
            try:
                body = await asyncio.wait_for(reader.readexactly(cl), timeout=10)
            except Exception:
                pass

        response, status, ct = await self._route(method, path, body)
        await self._write(writer, status, response, ct)
        try:
            writer.close()
        except Exception:
            pass

    async def _write(self, writer, status, body, ct="application/json"):
        if isinstance(body, str):
            body = body.encode()
        resp = (
            f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: {ct}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Cache-Control: no-store\r\n"
            f"Connection: close\r\n\r\n"
        ).encode() + body
        writer.write(resp)
        await writer.drain()

    async def _route(self, method, path, body):
        if path == "/" or path.startswith("/index"):
            return WEB_HTML, 200, "text/html; charset=utf-8"

        if path == "/api/snapshot":
            return json.dumps(self.state.get_snapshot()), 200, "application/json"

        if path.startswith("/api/events"):
            qs = _qs(path)
            since = int(qs.get("since", 0))
            events = self.state.events
            new = [e for e in events if e["seq"] > since]
            if not new:
                # short wait for new events
                try:
                    async with self.state._cond:
                        await asyncio.wait_for(self.state._cond.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
                new = [e for e in self.state.events if e["seq"] > since]
            return json.dumps(new), 200, "application/json"

        if path == "/api/hunt/start" and method == "POST":
            ok = self.state.start_hunt()
            return json.dumps({"ok": ok, "error": None if ok else "already running"}), 200, "application/json"

        if path == "/api/hunt/stop" and method == "POST":
            self.state.stop_hunt()
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/blacklist/add" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            self.state.blacklist_add(data.get("address", ""), data.get("reason", ""))
            return json.dumps({"ok": True}), 200, "application/json"

        if path == "/api/blacklist/remove" and method == "POST":
            try:
                data = json.loads(body or b"{}")
            except Exception:
                data = {}
            self.state.blacklist_remove(data.get("address", ""))
            return json.dumps({"ok": True}), 200, "application/json"

        # === Proxy routes ===
        if path == "/api/proxy/status":
            return json.dumps(self.proxy.get_status()), 200, "application/json"

        if path == "/api/proxy/alive":
            ratings = [r for r in self.state.ratings.values()
                       if r.last_status == "ok" and not r.in_blacklist]
            ratings.sort(key=lambda r: r.score, reverse=True)
            return json.dumps([r.to_dict() for r in ratings]), 200, "application/json"

        if path.startswith("/api/proxy/start"):
            qs = _qs(path)
            port = int(qs.get("port", 17277))
            await self.proxy.start(port)
            return json.dumps(self.proxy.get_status()), 200, "application/json"

        if path == "/api/proxy/stop":
            await self.proxy.stop()
            return json.dumps({"ok": True}), 200, "application/json"

        if path.startswith("/api/proxy/select"):
            qs = _qs(path)
            address = qs.get("address") or None
            self.proxy.select(address)
            return json.dumps({"ok": True, "address": address}), 200, "application/json"

        if path.startswith("/api/proxy/direct"):
            qs = _qs(path)
            en = qs.get("on", "true").lower() != "false"
            self.proxy.direct_mode = en
            if en:
                self.proxy.active_proxy_addr = None
            self.state._emit(f"Direct mode: {'ON' if en else 'OFF'}", "info")
            return json.dumps({"ok": True, "direct_mode": en}), 200, "application/json"

        if path.startswith("/api/settings/country_filter") and method == "POST":
            qs = _qs(path)
            code = qs.get("code", "").upper()
            self.state.country_filter = code
            self.state._emit(f"Country filter set to: {code or 'ALL'}", "info")
            return json.dumps({"ok": True, "country_filter": self.state.country_filter}), 200, "application/json"

        return json.dumps({"error": "not found"}), 404, "application/json"


def setup_logging():
    level = os.environ.get("SETPROXY_LOG_LEVEL", "INFO")
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")


async def amain(config: dict):
    hunt_cfg = config.get("hunt", {})
    host = hunt_cfg.get("web_listen_host", "127.0.0.1")
    port = hunt_cfg.get("web_listen_port", 17177)

    state = HuntState(hunt_cfg)
    server = HuntServer(state, host, port)

    print("=" * 56)
    print(f"  setproxy HUNT — web UI: http://{host}:{port}/")
    print(f"  data dir: {DATA_DIR}")
    print("  Ctrl+C to stop")
    print("=" * 56)

    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()


def main():
    setup_logging()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args, _ = ap.parse_known_args()

    if not CONFIG_PATH.exists():
        print(f"ERROR: {CONFIG_PATH} not found", file=__import__("sys").stderr)
        return

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    hunt_cfg = config.get("hunt", {})
    if args.host:
        hunt_cfg["web_listen_host"] = args.host
    if args.port:
        hunt_cfg["web_listen_port"] = args.port

    try:
        asyncio.run(amain(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
