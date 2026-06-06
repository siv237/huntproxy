"""
Hunt — proxy discovery + health-check controller with beautiful web UI.
Pure Python, asyncio, in-project data.
"""

import asyncio
import json
import logging
import os
import time
import yaml
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
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
        self.us_only = cfg.get("us_only", True)
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
                "us_only": self.us_only,
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
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, OSError):
            return False, ""
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
        if self.us_only and country != "United States":
            return False, country
        return True, country

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
# Web server
# ============================================================

WEB_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>setproxy · hunt</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#222;padding:20px;max-width:1400px;margin:0 auto}
h1{font-size:20px;margin-bottom:4px}
.sub{color:#888;font-size:12px;margin-bottom:16px}
.row{display:flex;gap:14px;flex-wrap:wrap}
.col{flex:1;min-width:280px}
.card{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:14px;margin-bottom:12px}
.card h2{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;font-weight:600}
.metric{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}
.metric .v{font-size:22px;font-weight:700}
.metric .l{font-size:11px;color:#656d76;text-transform:uppercase;letter-spacing:.5px}
.ok{color:#1a7f37} .warn{color:#9a6700} .err{color:#cf222e} .bl{color:#8250df}
button{font:inherit;cursor:pointer;padding:7px 14px;border:1px solid #d0d7de;border-radius:5px;background:#fff;color:#222}
button:hover{background:#e8eaed}
button:disabled{opacity:.4;cursor:default}
button.primary{background:#0969da;border-color:#0969da;color:#fff;font-weight:600;padding:8px 18px}
button.primary:hover{background:#0550ae}
button.danger{color:#cf222e;border-color:#cf222e}
button.danger:hover{background:#fff0f0}
.btnbar{display:flex;gap:8px;flex-wrap:wrap}
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
.log{font:11px/1.4 Menlo,Consolas,monospace;max-height:200px;overflow-y:auto;background:#f6f8fa;border:1px solid #d0d7de;border-radius:5px;padding:6px}
.log-line{padding:1px 0}
.log-ts{color:#888;margin-right:6px}
input[type=text]{border:1px solid #d0d7de;padding:5px 8px;border-radius:4px;font:13px inherit;width:100%}
input[type=text]:focus{outline:none;border-color:#0969da;box-shadow:0 0 0 2px #b6d4fe}
.bl-form{display:flex;gap:6px;margin-bottom:8px}
.empty{color:#888;font-style:italic;padding:14px;text-align:center}
.score-bar{display:inline-block;width:50px;height:5px;background:#e8eaed;border-radius:3px;vertical-align:middle;overflow:hidden}
.score-bar .s{height:100%;background:linear-gradient(90deg,#0969da,#8250df)}
.pulse{display:inline-block;width:8px;height:8px;border-radius:50%;background:#1a7f37;box-shadow:0 0 0 0 rgba(26,127,55,.5);animation:pulse 1.5s infinite;vertical-align:middle}
.pulse.off{background:#bbb;animation:none;box-shadow:none}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(26,127,55,.4)}70%{box-shadow:0 0 0 8px rgba(26,127,55,0)}100%{box-shadow:0 0 0 0 rgba(26,127,55,0)}}
</style>
</head>
<body>

<h1>setproxy &middot; proxy hunt</h1>
<div class="sub">
  <span class="phase" id="phase-badge">idle</span>
  &nbsp; <span id="last-event" style="color:#888">ready</span>
  <span class="pulse off" id="live-dot" style="margin-left:10px"></span>
</div>

<div class="row">
<div class="col" style="min-width:320px">

<div class="card">
<h2>control</h2>
<div class="btnbar">
<button class="primary" id="btn-start" onclick="start()">&#9654; Start Hunt</button>
<button class="danger" id="btn-stop" onclick="stop()" disabled>&#9632; Stop</button>
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
<div class="log" id="log"></div>
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

<script>
let lastEventSeq=0,logLines=[];

function flag(c){if(!c||c.length!==2)return'\u{1F3F3}';var b=0x1F1E6-'A'.charCodeAt(0);return String.fromCodePoint(b+c.charCodeAt(0),b+c.charCodeAt(1))}
function fmtTime(t){return new Date(t*1e3).toLocaleTimeString()}

async function api(p,m,g){var o={method:m||'GET',headers:{}};if(g){o.headers['Content-Type']='application/json';o.body=JSON.stringify(g)}return(await fetch(p,o)).json()}

async function start(){var r=await api('/api/hunt/start','POST');if(r.error)alert(r.error)}
async function stop(){await api('/api/hunt/stop','POST')}

async function blAdd(){var a=document.getElementById('bl-input').value.trim(),r=document.getElementById('bl-reason').value.trim();if(!a)return;await api('/api/blacklist/add','POST',{address:a,reason:r});document.getElementById('bl-input').value='';document.getElementById('bl-reason').value='';poll()}
async function blRemove(a){await api('/api/blacklist/remove','POST',{address:a});poll()}

function render(s){
['m-alive','m-dead','m-bl','m-total'].forEach(function(k,i){document.getElementById(k).textContent=[s.counts.alive,s.counts.dead,s.counts.blacklist,s.counts.ratings][i]});
var b=document.getElementById('phase-badge');b.textContent=s.phase;b.className='phase phase-'+s.phase;
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

// table
var tb=document.getElementById('top-body');
tb.innerHTML=s.top_proxies.length?s.top_proxies.map(function(p,i){var sc=Math.min(100,Math.max(0,p.score));return'<tr><td style="color:#656d76">'+(i+1)+'</td><td class="addr">'+p.address+'</td><td>'+flag(p.country_code)+' '+p.country+'</td><td>'+p.last_latency.toFixed(2)+'s</td><td>'+(p.success_rate*100).toFixed(0)+'%</td><td>'+p.checks_ok+'/'+p.checks_total+'</td><td><div class="score-bar"><div class="s" style="width:'+sc+'%"></div></div></td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+p.address+'\')">bl</button></td></tr>'}).join(''):'<tr><td colspan="8" class="empty">no alive proxies</td></tr>';

var bb=document.getElementById('bl-body');
bb.innerHTML=s.blacklist.length?s.blacklist.map(function(b){return'<tr><td class="addr">'+b.address+'</td><td style="color:#8250df">'+(b.reason||'\u2014')+'</td><td>'+(b.country||'\u2014')+'</td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+b.address+'\')">\u00d7</button></td></tr>'}).join(''):'<tr><td colspan="4" class="empty">no entries</td></tr>';
}

function renderLog(ev){ev.forEach(function(e){lastEventSeq=Math.max(lastEventSeq,e.seq);logLines.unshift('<span class="log-ts">'+fmtTime(e.ts)+'</span><span class="log-line '+e.type+'">'+e.type.padEnd(8)+'</span> '+e.msg);if(logLines.length>200)logLines.length=200});document.getElementById('log').innerHTML=logLines.map(function(l){return'<div>'+l+'</div>'}).join('')}

async function poll(){try{render(await api('/api/snapshot'))}catch(e){}try{var ev=await api('/api/events?since='+lastEventSeq);if(ev.length)renderLog(ev)}catch(e){}}
poll();setInterval(poll,600);
</script>
</body>
</html>"""


class HuntServer:
    def __init__(self, state: HuntState, host: str, port: int):
        self.state = state
        self.host = host
        self.port = port
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
            since = 0
            if "?" in path:
                for p in path.split("?")[1].split("&"):
                    if p.startswith("since="):
                        try: since = int(p.split("=")[1])
                        except: pass
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
