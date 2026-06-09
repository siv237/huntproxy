"""
Hunt — proxy discovery + health-check controller with beautiful web UI.
Pure Python, asyncio, in-project data.
"""

import asyncio
import json
import logging
import os
import socket
import sqlite3
import struct
import time
import yaml
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.yaml"
DATA_DIR = PROJECT_DIR / "data"
HUNT_HTML_PATH = PROJECT_DIR / "hunt.html"
WEB_DIR = PROJECT_DIR / "web"

STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
}

logger = logging.getLogger("huntproxy.hunt")

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
    last_ok: float = 0.0
    last_latency: float = 0.0
    last_status: str = "untested"  # ok / failed / untested
    first_seen: float = 0.0
    in_blacklist: bool = False
    blacklist_reason: str = ""
    supports_connect: bool = False
    mitm_suspect: bool = False
    egress_ip: str = ""
    egress_city: str = ""
    egress_isp: str = ""
    egress_country: str = ""
    listen_country: str = ""
    listen_city: str = ""
    listen_isp: str = ""
    egress_http_ip: str = ""
    egress_http_country: str = ""
    speed_sum: float = 0.0
    speed_count: int = 0
    last_speed: float = 0.0
    speed_fails: int = 0

    @property
    def speed_avg(self) -> float:
        return self.speed_sum / self.speed_count if self.speed_count else 0.0

    @property
    def latency_avg(self) -> float:
        return self.latency_sum / self.latency_count if self.latency_count else 0.0

    @property
    def success_rate(self) -> float:
        return self.checks_ok / self.checks_total if self.checks_total else 0.0

    @property
    def score(self) -> float:
        if self.checks_total == 0 or self.last_status != "ok":
            return 0.0
        sr = self.success_rate
        base = sr * 50
        if self.latency_count == 0:
            lat_score = 50
        else:
            lat_score = max(0, 100 - self.latency_avg * 10)
        result = base + lat_score * 0.5
        if self.supports_connect:
            result += 15
        if self.mitm_suspect:
            result -= 30
        if self.speed_count > 0:
            result += min(20, self.speed_avg / 50)
        if self.speed_fails >= 3:
            result -= 40
        return max(0, result)

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
            "speed_avg": round(self.speed_avg, 1),
            "last_speed": round(self.last_speed, 1),
            "speed_sum": round(self.speed_sum, 1),
            "speed_count": self.speed_count,
            "speed_fails": self.speed_fails,
            "last_check": self.last_check,
            "last_status": self.last_status,
            "first_seen": self.first_seen,
            "in_blacklist": self.in_blacklist,
            "blacklist_reason": self.blacklist_reason,
            "supports_connect": self.supports_connect,
            "mitm_suspect": self.mitm_suspect,
            "last_check_ago": round(time.time() - self.last_check, 1) if self.last_check else 0,
            "last_ok": self.last_ok,
            "egress_ip": self.egress_ip,
            "egress_city": self.egress_city,
            "egress_isp": self.egress_isp,
            "egress_country": self.egress_country,
            "listen_country": self.listen_country,
            "listen_city": self.listen_city,
            "listen_isp": self.listen_isp,
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
        self._geo_cache: dict[str, dict] = {}
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

        self.started_at = time.time()
        self._db_path = DATA_DIR / "stats.db"
        self._last_history_ts = time.time()
        self._init_db()
        try:
            conn = self._db()
            row = conn.execute("SELECT MAX(ts) as last_ts FROM history").fetchone()
            conn.close()
            if row and row["last_ts"]:
                self._last_history_ts = row["last_ts"]
        except Exception:
            pass
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

    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._db()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                alive INTEGER DEFAULT 0,
                dead INTEGER DEFAULT 0,
                total INTEGER DEFAULT 0,
                requests INTEGER DEFAULT 0,
                connections_ok INTEGER DEFAULT 0,
                connections_failed INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0,
                traffic_success_rate REAL DEFAULT 0,
                bandwidth_in INTEGER DEFAULT 0,
                bandwidth_out INTEGER DEFAULT 0,
                avg_latency REAL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_history_ts ON history(ts);
            CREATE TABLE IF NOT EXISTS traffic_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                client TEXT DEFAULT '',
                target TEXT DEFAULT '',
                status TEXT DEFAULT '',
                upstream TEXT DEFAULT '',
                bytes_in INTEGER DEFAULT 0,
                bytes_out INTEGER DEFAULT 0,
                duration REAL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_traffic_ts ON traffic_log(ts);
            CREATE INDEX IF NOT EXISTS idx_traffic_target ON traffic_log(target);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                seq INTEGER DEFAULT 0,
                type TEXT DEFAULT 'info',
                msg TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        """)
        conn.commit()
        for col, default in [
            ("traffic_success_rate", "REAL DEFAULT 0"),
            ("bandwidth_in", "INTEGER DEFAULT 0"),
            ("bandwidth_out", "INTEGER DEFAULT 0"),
            ("avg_latency", "REAL DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE history ADD COLUMN {col} {default}")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def _emit(self, msg: str, kind: str = "info", **kwargs):
        self._event_seq += 1
        ts = time.time()
        ev = {"seq": self._event_seq, "ts": ts, "type": kind, "msg": msg}
        ev.update(kwargs)
        self.events.append(ev)
        if len(self.events) > 500:
            self.events = self.events[-300:]
        self.last_event = msg
        try:
            conn = self._db()
            conn.execute("INSERT INTO events (ts, seq, type, msg) VALUES (?,?,?,?)", (ts, self._event_seq, kind, msg))
            conn.commit()
            conn.close()
        except Exception:
            pass
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
                "new_today": sum(1 for r in self.ratings.values() if r.first_seen > time.time() - 86400),
            },
            "settings": {
                "parallel": self.parallel,
                "timeout": self.timeout,
                "country_filter": self.country_filter,
            },
            "top_proxies": [r.to_dict() for r in sorted_alive[:30]],
            "blacklist": self._blacklist_view(),
            "last_event": self.last_event,
            "uptime_seconds": int(time.time() - self.started_at),
            "last_proxy_details": self.ratings.get(self.last_proxy, ProxyRating(address=self.last_proxy or "")).to_dict() if self.last_proxy else None,
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

    def get_countries(self) -> list:
        alive = [r for r in self.ratings.values() if r.last_status == "ok" and not r.in_blacklist and r.country]
        counts = Counter(r.country for r in alive)
        total = sum(counts.values()) or 1
        result = []
        for country, count in counts.most_common(10):
            code = country_code_from_name(country)
            result.append({"country": country, "country_code": code, "count": count, "pct": round(count / total * 100, 1)})
        return result

    def get_activity(self, limit: int = 10) -> list:
        def _icon(kind, msg):
            if "validated" in msg.lower(): return "validated"
            if "added" in msg.lower(): return "added"
            if "removed" in msg.lower() or "clear" in msg.lower(): return "removed"
            if "failed" in msg.lower() or "error" in msg.lower(): return "failed"
            if "health" in msg.lower(): return "health"
            if "blacklist" in msg.lower(): return "blacklist"
            if "stopped" in msg.lower(): return "stopped"
            if "started" in msg.lower(): return "started"
            return "info"
        out = []
        if self.events:
            for ev in reversed(self.events[-limit:]):
                out.append({
                    "seq": ev["seq"],
                    "ts": ev["ts"],
                    "type": ev["type"],
                    "msg": ev["msg"],
                    "icon": _icon(ev["type"], ev["msg"]),
                })
        else:
            try:
                conn = self._db()
                rows = conn.execute("SELECT ts, seq, type, msg FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                conn.close()
                for r in rows:
                    out.append({"seq": r["seq"], "ts": r["ts"], "type": r["type"], "msg": r["msg"], "icon": _icon(r["type"], r["msg"])})
            except Exception:
                pass
        return out

    def get_history(self, last: str = "1h") -> list:
        try:
            if last.endswith("h"):
                cutoff = time.time() - int(last[:-1]) * 3600
            elif last.endswith("d"):
                cutoff = time.time() - int(last[:-1]) * 86400
            else:
                cutoff = 0
        except Exception:
            cutoff = 0
        try:
            conn = self._db()
            rows = conn.execute(
                "SELECT ts, alive, dead, total, requests, connections_ok, connections_failed, success_rate, traffic_success_rate, bandwidth_in, bandwidth_out, avg_latency FROM history WHERE ts > ? ORDER BY ts",
                (cutoff,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("DB get_history: %s", e)
            return []

    def _get_system(self) -> dict:
        try:
            import psutil
            return {
                "cpu": psutil.cpu_percent(interval=0.1),
                "mem": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent,
            }
        except Exception:
            pass
        # Fallback Linux /proc
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            parts = line.split()
            if parts[0] == "cpu" and len(parts) >= 5:
                idle = int(parts[4])
                total = sum(int(x) for x in parts[1:5])
                cpu = round((1 - idle / total) * 100, 1) if total else 0.0
            else:
                cpu = 0.0
        except Exception:
            cpu = None
        try:
            with open("/proc/meminfo") as f:
                mem_total = None
                mem_avail = None
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_avail = int(line.split()[1])
                if mem_total and mem_avail:
                    mem = round((1 - mem_avail / mem_total) * 100, 1)
                else:
                    mem = None
        except Exception:
            mem = None
        try:
            import shutil
            du = shutil.disk_usage('/')
            disk = round(du.used / du.total * 100, 1)
        except Exception:
            disk = None
        return {"cpu": cpu, "mem": mem, "disk": disk}

    def _push_history(self):
        alive = sum(1 for r in self.ratings.values() if r.last_status == "ok" and not r.in_blacklist)
        dead = sum(1 for r in self.ratings.values() if r.last_status == "failed")
        pool_sr = (alive / max(1, alive + dead)) * 100

        since = getattr(self, '_last_history_ts', time.time() - 60)
        now = time.time()
        total_req = 0
        ok_req = 0
        bw_in = 0
        bw_out = 0
        avg_lat = 0.0
        try:
            conn = self._db()
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) as ok, "
                "COALESCE(SUM(bytes_in), 0) as bw_in, "
                "COALESCE(SUM(bytes_out), 0) as bw_out, "
                "COALESCE(AVG(CASE WHEN duration > 0 THEN duration END), 0) as avg_lat "
                "FROM traffic_log WHERE ts > ?",
                (since,)
            ).fetchone()
            conn.close()
            if row:
                total_req = row["total"] or 0
                ok_req = row["ok"] or 0
                bw_in = row["bw_in"] or 0
                bw_out = row["bw_out"] or 0
                avg_lat = row["avg_lat"] or 0.0
        except Exception as e:
            logger.error("DB traffic query: %s", e)

        traffic_sr = (ok_req / max(1, total_req)) * 100 if total_req else 0

        try:
            conn = self._db()
            conn.execute(
                "INSERT INTO history (ts, alive, dead, total, requests, connections_ok, connections_failed, success_rate, traffic_success_rate, bandwidth_in, bandwidth_out, avg_latency) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (now, alive, dead, len(self.ratings), total_req, ok_req, total_req - ok_req, pool_sr, traffic_sr, bw_in, bw_out, avg_lat)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("DB push history: %s", e)

        self._last_history_ts = now

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
        self._save_state()
        self._save_working_file()
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
                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency = await self._check_proxy(addr)
                speed = 0.0
                if ok:
                    host, port_str = addr.rsplit(":", 1)
                    try:
                        speed = await self._measure_speed(host, int(port_str),
                                                           port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145))
                    except Exception:
                        speed = 0.0
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
                    self._update_rating(addr, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed)
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
        self._push_history()

    async def _check_proxy(self, addr: str) -> tuple:
        host, port_str = addr.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return False, "", False, False, {}, {}, 0.0
        is_socks = port in (1080, 10808, 9050, 4145)

        t0 = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
        except (asyncio.TimeoutError, OSError):
            return False, "", False, False, {}, {}, 0.0

        listen_task = asyncio.create_task(self._resolve_geo(host))
        country = ""
        country_code = ""
        supports_connect = False
        mitm_suspect = False
        egress: dict = {}

        if is_socks:
            if port == 4145:
                ok = await self._socks4_test(reader, writer)
            else:
                ok = await self._socks5_test(reader, writer)
            try: writer.close()
            except: pass
            if not ok:
                listen = await listen_task
                return False, "", False, False, {}, listen, 0.0
            egress = await self._socks_egress(host, port)
            if egress:
                country = egress.get("egress_country", "")
                country_code = country_code_from_name(country)
            if not country:
                country = "Unknown"
            supports_connect = True
            http_latency = time.monotonic() - t0
        else:
            try:
                req = (
                    "GET http://ip-api.com/json/ HTTP/1.0\r\n"
                    "Host: ip-api.com\r\n"
                    "User-Agent: huntproxy\r\n"
                    "Connection: close\r\n"
                    "\r\n"
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
                listen = await listen_task
                return False, "", False, False, {}, listen, 0.0
            finally:
                try:
                    writer.close()
                except Exception:
                    pass

            sep = buf.find(b"\r\n\r\n")
            if sep == -1:
                sep = buf.find(b"\n\n")
            if sep == -1:
                listen = await listen_task
                return False, "", False, False, {}, listen, 0.0
            try:
                data = json.loads(buf[sep:].strip())
            except Exception:
                listen = await listen_task
                return False, "", False, False, {}, listen, 0.0
            country = data.get("country", "")
            country_code = data.get("countryCode", "")
            http_latency = time.monotonic() - t0
            egress = {
                "egress_ip": data.get("query", ""),
                "egress_city": data.get("city", ""),
                "egress_isp": data.get("isp", ""),
                "egress_country": data.get("country", ""),
            }

        listen = await listen_task
        if self.country_filter and country_code != self.country_filter:
            return False, country, False, False, egress, listen, 0.0
        if self.us_only and country != "United States":
            return False, country, False, False, egress, listen, 0.0

        connect_ok, mitm_suspect = await self._check_proxy_connect(host, port, is_socks)
        supports_connect = connect_ok

        if not connect_ok and not is_socks:
            return True, country, False, mitm_suspect, egress, listen, http_latency

        if not connect_ok:
            return False, country, False, mitm_suspect, egress, listen, http_latency
        return True, country, True, mitm_suspect, egress, listen, http_latency

    async def _check_proxy_connect(self, host: str, port: int, is_socks: bool = False) -> tuple:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=self.timeout)
        except Exception:
            return False, False
        try:
            if is_socks:
                if port == 4145:
                    ok = await self._socks4_test(r, w)
                else:
                    ok = await self._socks5_test(r, w)
                if ok:
                    mitm = await self._check_mitm_socks(r, w, port)
                    return ok, mitm
                return ok, False
            else:
                req = f"CONNECT 2ip.ru:443 HTTP/1.1\r\nHost: 2ip.ru:443\r\n\r\n"
                w.write(req.encode())
                await asyncio.wait_for(w.drain(), timeout=self.timeout)
                try:
                    resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
                    if b"200" not in resp.split(b"\r\n")[0]:
                        return False, False
                except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                    return False, False

                mitm = await self._check_mitm_http(r, w)
                return True, mitm
        except Exception:
            return False, False
        finally:
            try:
                w.close()
            except Exception:
                pass

    SPEED_SERVERS = [
        ("speedtest.tele2.net", "/512KB.zip", 524288),
        ("ipv4.download.thinkbroadband.com", "/512KB.zip", 524288),
        ("testdebit.info", "/1M.iso", 1048576),
    ]

    async def _measure_speed(self, host: str, port: int, is_socks: bool = False) -> float:
        for srv_host, srv_path, expected_size in self.SPEED_SERVERS:
            speed = await self._speed_single(host, port, is_socks, srv_host, srv_path, expected_size)
            if speed > 0:
                return speed
        return 0.0

    async def _speed_single(self, host: str, port: int, is_socks: bool,
                             srv_host: str, srv_path: str, expected_size: int) -> float:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=self.timeout)
        except Exception:
            return 0.0
        try:
            if is_socks:
                if port == 4145:
                    ok = await self._socks4_test(r, w)
                else:
                    ok = await self._socks5_test(r, w)
                if not ok:
                    return 0.0
            t0 = time.monotonic()
            req = (
                f"GET http://{srv_host}{srv_path} HTTP/1.0\r\n"
                f"Host: {srv_host}\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            w.write(req.encode())
            await asyncio.wait_for(w.drain(), timeout=10)
            total = 0
            while True:
                try:
                    chunk = await asyncio.wait_for(r.read(65536), timeout=30)
                except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                    break
                if not chunk:
                    break
                total += len(chunk)
                if total >= expected_size:
                    break
            elapsed = time.monotonic() - t0
            if elapsed > 0 and total >= expected_size * 0.8:
                return total / elapsed / 1024.0
            return 0.0
        except Exception:
            return 0.0
        finally:
            try:
                w.close()
            except Exception:
                pass

    async def _check_mitm_http(self, r, w) -> bool:
        try:
            addr = w.transport.get_extra_info('peername')
            if not addr: return False
            host, port = addr
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sSf", "--max-time", "10",
                "-o", "/dev/null", "-w", "%{ssl_verify_result}",
                "-x", f"http://{host}:{port}",
                "https://2ip.ru",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return True
            verify = stdout.decode().strip()
            return verify != "0"
        except Exception:
            return False

    async def _check_mitm_socks(self, r, w, port: int = 0) -> bool:
        try:
            addr = r._transport.get_extra_info('peername')
            if not addr: return False
            host, _ = addr
            if port in (4145,):
                proto = "socks4a"
            else:
                proto = "socks5h"
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sSf", "--max-time", "10",
                "-o", "/dev/null", "-w", "%{ssl_verify_result}",
                "-x", f"{proto}://{host}:{port}",
                "https://2ip.ru",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode != 0:
                return True
            verify = stdout.decode().strip()
            return verify != "0"
        except Exception:
            return False

    async def _socks5_test(self, r, w) -> bool:
        try:
            w.write(bytes([5, 1, 0])); await w.drain()
            resp = await asyncio.wait_for(r.readexactly(2), timeout=8)
            if resp[1] != 0: return False
            req = bytes([5, 1, 0, 3, 13]) + b"httpbin.org" + b"\x01\xbb"
            w.write(req); await w.drain()
            hdr = await asyncio.wait_for(r.readexactly(4), timeout=8)
            if hdr[1] != 0: return False
            atyp = hdr[3]
            if atyp == 1:
                await asyncio.wait_for(r.readexactly(6), timeout=8)
            elif atyp == 3:
                dl = await asyncio.wait_for(r.readexactly(1), timeout=8)
                await asyncio.wait_for(r.readexactly(dl[0] + 2), timeout=8)
            elif atyp == 4:
                await asyncio.wait_for(r.readexactly(18), timeout=8)
            else:
                return False
            return True
        except Exception:
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

    async def _resolve_geo(self, ip: str) -> dict:
        if ip in self._geo_cache:
            return self._geo_cache[ip]
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection("ip-api.com", 80), timeout=5)
        except Exception:
            return {}
        try:
            req = f"GET /json/{ip} HTTP/1.0\r\nHost: ip-api.com\r\nUser-Agent: huntproxy\r\nConnection: close\r\n\r\n"
            w.write(req.encode())
            await asyncio.wait_for(w.drain(), timeout=5)
            buf = b""
            while True:
                try:
                    chunk = await asyncio.wait_for(r.read(4096), timeout=5)
                except asyncio.TimeoutError:
                    break
                if not chunk:
                    break
                buf += chunk
                if buf.count(b"}") >= 1 and len(buf) > 200:
                    break
        except Exception:
            return {}
        finally:
            try:
                w.close()
            except Exception:
                pass
        sep = buf.find(b"\r\n\r\n")
        if sep == -1:
            sep = buf.find(b"\n\n")
        if sep == -1:
            return {}
        try:
            data = json.loads(buf[sep:].strip())
        except Exception:
            return {}
        result = {
            "country": data.get("country", ""),
            "city": data.get("city", ""),
            "isp": data.get("isp", ""),
        }
        self._geo_cache[ip] = result
        return result

    async def _socks_egress(self, host: str, port: int) -> dict:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=self.timeout)
        except Exception:
            return {}
        try:
            if port == 4145:
                req = bytes([4, 1, 0, 80, 0, 0, 0, 1]) + b"\x00" + b"ip-api.com\x00"
                w.write(req); await asyncio.wait_for(w.drain(), timeout=8)
                resp = await asyncio.wait_for(r.readexactly(8), timeout=8)
                if resp[1] != 0x5A:
                    return {}
            else:
                w.write(bytes([5, 1, 0])); await asyncio.wait_for(w.drain(), timeout=8)
                resp = await asyncio.wait_for(r.readexactly(2), timeout=8)
                if resp[1] != 0:
                    return {}
                req = bytes([5, 1, 0, 3, 9]) + b"ip-api.com" + b"\x00\x50"
                w.write(req); await asyncio.wait_for(w.drain(), timeout=8)
                hdr = await asyncio.wait_for(r.readexactly(4), timeout=8)
                if hdr[1] != 0:
                    return {}
                atyp = hdr[3]
                if atyp == 1:
                    await asyncio.wait_for(r.readexactly(6), timeout=8)
                elif atyp == 3:
                    dl = await asyncio.wait_for(r.readexactly(1), timeout=8)
                    await asyncio.wait_for(r.readexactly(dl[0] + 2), timeout=8)
                elif atyp == 4:
                    await asyncio.wait_for(r.readexactly(18), timeout=8)
                else:
                    return {}
            w.write(b"GET /json/ HTTP/1.0\r\nHost: ip-api.com\r\nUser-Agent: huntproxy\r\nConnection: close\r\n\r\n")
            await asyncio.wait_for(w.drain(), timeout=8)
            buf = b""
            while True:
                try:
                    chunk = await asyncio.wait_for(r.read(4096), timeout=8)
                except asyncio.TimeoutError:
                    break
                if not chunk:
                    break
                buf += chunk
                if buf.count(b"}") >= 1 and len(buf) > 200:
                    break
        except Exception:
            return {}
        finally:
            try:
                w.close()
            except Exception:
                pass
        sep = buf.find(b"\r\n\r\n")
        if sep == -1:
            sep = buf.find(b"\n\n")
        if sep == -1:
            return {}
        try:
            data = json.loads(buf[sep:].strip())
        except Exception:
            return {}
        return {
            "egress_ip": data.get("query", ""),
            "egress_city": data.get("city", ""),
            "egress_isp": data.get("isp", ""),
            "egress_country": data.get("country", ""),
        }

    def _update_rating(self, addr: str, ok: bool, country: str, latency: float,
                        supports_connect: bool = False, mitm_suspect: bool = False,
                        egress: dict = None, listen: dict = None,
                        speed: float = 0.0):
        r = self.ratings.get(addr)
        if not r:
            r = ProxyRating(
                address=addr,
                country=country,
                country_code=country_code_from_name(country),
                first_seen=time.time(),
            )
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
            r.last_ok = time.time()
            if speed > 0:
                r.speed_sum += speed
                r.speed_count += 1
                r.last_speed = speed
                r.speed_fails = 0
            else:
                r.speed_fails += 1
            if country and not r.country:
                r.country = country
                r.country_code = country_code_from_name(country)
            r.supports_connect = supports_connect
            if mitm_suspect:
                r.mitm_suspect = True
            if egress:
                r.egress_ip = egress.get("egress_ip") or r.egress_ip
                r.egress_city = egress.get("egress_city") or r.egress_city
                r.egress_isp = egress.get("egress_isp") or r.egress_isp
                r.egress_country = egress.get("egress_country") or r.egress_country
            if listen:
                r.listen_country = listen.get("country") or r.listen_country
                r.listen_city = listen.get("city") or r.listen_city
                r.listen_isp = listen.get("isp") or r.listen_isp
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

    async def _history_loop(self):
        while True:
            await asyncio.sleep(60)
            try:
                self._push_history()
            except Exception:
                pass
            try:
                conn = self._db()
                cutoff_traffic = time.time() - 7 * 86400
                cutoff_events = time.time() - 30 * 86400
                conn.execute("DELETE FROM traffic_log WHERE ts < ?", (cutoff_traffic,))
                conn.execute("DELETE FROM events WHERE ts < ?", (cutoff_events,))
                conn.commit()
                conn.close()
            except Exception:
                pass

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
                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency = await self._check_proxy(r.address)
                speed = 0.0
                if ok:
                    host, port_str = r.address.rsplit(":", 1)
                    try:
                        speed = await self._measure_speed(host, int(port_str),
                                                           port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145))
                    except Exception:
                        speed = 0.0
                async with lock:
                    self.checked += 1
                    if ok:
                        ok_count += 1
                        self.working = ok_count
                    else:
                        fail_count += 1
                        self.failed = fail_count
                    self._update_rating(r.address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed)

        tasks = [asyncio.create_task(check(r)) for r in candidates]
        await asyncio.gather(*tasks)
        self._save_state()
        self._save_working_file()
        self._push_history()
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
            f.write(f"# huntproxy blacklist (operator-curated, NOT dead proxies)\n")
            for addr, reason in sorted(self.blacklist.items()):
                f.write(f"{addr}  {reason}\n")

    def _load_state(self):
        sf = self.state_file
        if not sf.exists():
            return
        try:
            data = json.loads(sf.read_text())
            if isinstance(data, dict):
                proxies = data.get("proxies", [])
                pr = data.get("proxy_runner", {})
                self._proxy_direct_mode = pr.get("direct_mode", False)
                self._proxy_active_addr = pr.get("active_proxy_addr")
            elif isinstance(data, list):
                proxies = data
            else:
                return
            for d in proxies:
                r = ProxyRating(
                    address=d["address"],
                    country=d.get("country", ""),
                    country_code=d.get("country_code", ""),
                    protocol=d.get("protocol", "http"),
                    latency_sum=d.get("latency_avg", 0) * d.get("checks_ok", 0),
                    latency_count=d.get("checks_ok", 0),
                    last_latency=d.get("last_latency", 0),
                    checks_total=d.get("checks_total", 0),
                    checks_ok=d.get("checks_ok", 0),
                    last_check=d.get("last_check", 0),
                    last_ok=d.get("last_ok", 0),
                    last_status=d.get("last_status", "untested"),
                    first_seen=d.get("first_seen", 0),
                    supports_connect=d.get("supports_connect", False),
                    mitm_suspect=d.get("mitm_suspect", False),
                    last_speed=d.get("last_speed", 0.0),
                    speed_sum=d.get("speed_sum", 0),
                    speed_count=d.get("speed_count", 0),
                    speed_fails=d.get("speed_fails", 0),
                    egress_http_ip=d.get("egress_http_ip", ""),
                    egress_http_country=d.get("egress_http_country", ""),
                    egress_ip=d.get("egress_ip", ""),
                    egress_city=d.get("egress_city", ""),
                    egress_isp=d.get("egress_isp", ""),
                    egress_country=d.get("egress_country", ""),
                    listen_country=d.get("listen_country", ""),
                    listen_city=d.get("listen_city", ""),
                    listen_isp=d.get("listen_isp", ""),
                )
                self.ratings[r.address] = r
            logger.info(f"Loaded {len(self.ratings)} ratings from state file")
        except Exception as e:
            logger.warning(f"State load failed: {e}")

    def _save_state(self):
        data = {
            "proxies": [r.to_dict() for r in self.ratings.values()],
            "proxy_runner": {
                "direct_mode": getattr(self, '_proxy_direct_mode', False),
                "active_proxy_addr": getattr(self, '_proxy_active_addr', None),
            }
        }
        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

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
    def __init__(self, state: "HuntState", host: str = "127.0.0.1"):
        self.state = state
        self.proxy_host = host
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
                self._handle, self.proxy_host, self.port)
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
        t0 = time.monotonic()
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
                    dur = time.monotonic() - t0
                    self._log(peer, target_host, "502 no upstream", duration=dur)
                    return

                up_r, up_w, up_addr = upstream
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                bi, bo = await self._relay(reader, up_w, up_r, writer)
                dur = time.monotonic() - t0
                self._log(peer, target_host, "ok", up_addr, bytes_in=bi, bytes_out=bo, duration=dur)
            else:
                await self._handle_http_forward(reader, writer, method, parts[1], peer, t0)
        except Exception as e:
            dur = time.monotonic() - t0
            self._log(peer, target_host, f"err: {e}", duration=dur)
        finally:
            try: writer.close()
            except: pass

    async def _handle_http_forward(self, reader, writer, method, url, peer, t0):
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
            dur = time.monotonic() - t0
            self._log(peer, target_host, "502 no upstream", duration=dur); return

        up_r, up_w, up_addr = upstream

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
        bi, bo = await self._relay(up_r, writer, reader, up_w)
        dur = time.monotonic() - t0
        self._log(peer, target_host, "ok", up_addr, bytes_in=bi, bytes_out=bo, duration=dur)

    async def _connect_upstream(self, host: str, port: int):
        if self.direct_mode:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=15)
                return reader, writer, "direct"
            except Exception:
                return None

        if self.active_proxy_addr:
            r = self.state.ratings.get(self.active_proxy_addr)
            if not r or r.in_blacklist:
                return None
            phost, pport_str = r.address.rsplit(":", 1)
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str)), timeout=10)
            except Exception:
                return None
            if r.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
            elif r.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
            else:
                ok = await self._http_connect_cmd(reader, writer, host, port)
            if not ok:
                try: writer.close()
                except: pass
                return None
            return reader, writer, r.address

        pool = [r for r in self.state.ratings.values()
                if r.last_status == "ok" and not r.in_blacklist]
        if not pool:
            return None
        pool.sort(key=lambda r: r.score, reverse=True)

        for attempt in range(min(len(pool), 8)):
            p = pool[attempt]

            phost, pport_str = p.address.rsplit(":", 1)
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str)), timeout=10)
            except Exception:
                continue

            ok = False
            if p.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
            elif p.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
            else:
                ok = await self._http_connect_cmd(reader, writer, host, port)

            if not ok:
                try: writer.close()
                except: pass
                continue

            self._failover_idx = (attempt + 1) % len(pool)
            return reader, writer, p.address

        return None

    async def _http_connect_cmd(self, r, w, h, p):
        req = f"CONNECT {h}:{p} HTTP/1.1\r\nHost: {h}:{p}\r\n\r\n"
        w.write(req.encode()); await w.drain()
        try:
            resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
            status_line = resp.split(b"\r\n")[0]
            return b"200" in status_line
        except asyncio.TimeoutError:
            return False
        except Exception:
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
            hdr = await asyncio.wait_for(r.readexactly(4), timeout=8)
            if hdr[1] != 0: return False
            atyp = hdr[3]
            if atyp == 1:
                await asyncio.wait_for(r.readexactly(4 + 2), timeout=8)
            elif atyp == 3:
                dl = await asyncio.wait_for(r.readexactly(1), timeout=8)
                await asyncio.wait_for(r.readexactly(dl[0] + 2), timeout=8)
            elif atyp == 4:
                await asyncio.wait_for(r.readexactly(16 + 2), timeout=8)
            else:
                return False
            return True
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
        bytes_in = 0
        bytes_out = 0
        async def pipe(r, w, label):
            nonlocal bytes_in, bytes_out
            try:
                while True:
                    data = await r.read(65536)
                    if not data: break
                    n = len(data)
                    if label == "c2u":
                        bytes_in += n
                    else:
                        bytes_out += n
                    w.write(data); await w.drain()
            except: pass
            finally:
                try: w.close()
                except: pass
        await asyncio.gather(pipe(r1, w1, "c2u"), pipe(r2, w2, "u2c"))
        return bytes_in, bytes_out

    def _log(self, peer, target, status, upstream="", bytes_in=0, bytes_out=0, duration=0.0):
        entry = {"ts": time.time(), "client": f"{peer[0]}:{peer[1]}" if peer else "?", "target": target, "status": status, "upstream": upstream, "bytes_in": bytes_in, "bytes_out": bytes_out, "duration": round(duration, 3)}
        self.log.append(entry)
        if len(self.log) > 200:
            self.log = self.log[-150:]
        try:
            conn = self.state._db()
            conn.execute("INSERT INTO traffic_log (ts, client, target, status, upstream, bytes_in, bytes_out, duration) VALUES (?,?,?,?,?,?,?,?)",
                         (entry["ts"], entry["client"], target, status, upstream, bytes_in, bytes_out, round(duration, 3)))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_status(self) -> dict:
        ok = sum(1 for e in self.log if e["status"] == "ok")
        failed = len(self.log) - ok
        return {
            "running": self.running,
            "port": self.port,
            "bind_host": self.proxy_host,
            "active_proxy": self.selected_proxy.to_dict() if self.selected_proxy else None,
            "direct_mode": self.direct_mode,
            "connections": len(self.log),
            "connections_ok": ok,
            "connections_failed": failed,
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
<title>huntproxy</title>
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
th,td{text-align:left;padding:4px 6px;border-bottom:1px solid #d0d7de}
th{color:#656d76;font-weight:500;font-size:10px;text-transform:uppercase;letter-spacing:.5px;position:sticky;top:0;background:#f6f8fa}
th.sortable{cursor:pointer;user-select:none}th.sortable:hover{color:#0969da}
tbody tr:hover{background:#eef1f5}
.tbl-wrap{max-height:400px;overflow-y:auto;border-radius:6px}
.addr{font-family:Menlo,Consolas,monospace;color:#0969da;max-width:125px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.live{font:11px/1.4 Menlo,Consolas,monospace;max-height:200px;overflow-y:auto;background:#f6f8fa;border:1px solid #d0d7de;border-radius:5px;padding:6px}
.live div{padding:1px 0}
.live-ts{color:#888;margin-right:6px}
input[type=text],input[type=number]{border:1px solid #d0d7de;padding:5px 8px;border-radius:4px;font:13px inherit;width:100%}
input[type=text]:focus,input[type=number]:focus{outline:none;border-color:#0969da;box-shadow:0 0 0 2px #b6d4fe}
.bl-form{display:flex;gap:6px;margin-bottom:8px}
.empty{color:#888;font-style:italic;padding:14px;text-align:center}
.empty.small{padding:6px;font-size:11px}
.score-bar{display:inline-block;width:40px;height:5px;background:#e8eaed;border-radius:3px;vertical-align:middle;overflow:hidden}
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

<h1>huntproxy</h1>
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

<div class="col" style="min-width:540px">

<div class="card">
 <h2>top rated alive</h2>
<div class="tbl-wrap">
<table>
<thead><tr>
<th>#</th><th class="sortable" onclick="sortTop('address')">proxy</th><th class="sortable" onclick="sortTop('country')">country</th>      <th class="sortable" onclick="sortTop('last_latency')">latency</th><th class="sortable" onclick="sortTop('latency_avg')">avg</th><th class="sortable" onclick="sortTop('speed_avg')" title="KB/s">KB/s</th><th class="sortable" onclick="sortTop('success_rate')">success</th><th class="sortable" onclick="sortTop('checks_ok')">checks</th><th class="sortable" onclick="sortTop('score')">score</th><th class="sortable" onclick="sortTop('supports_connect')">flags</th><th class="sortable" onclick="sortTop('last_ok')" style="width:48px">ok</th><th></th>
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
  <div class="sel-geo" id="sel-geo" style="font-size:11px;color:#656d76;margin-bottom:8px;line-height:1.6"></div>
  <div class="sel-stats" id="sel-stats">
     <div class="metric"><div class="v" id="sel-score">-</div><div class="l">score</div></div>
     <div class="metric"><div class="v" id="sel-lat">-</div><div class="l">latency</div></div>
     <div class="metric"><div class="v" id="sel-speed">-</div><div class="l">KB/s</div></div>
     <div class="metric"><div class="v" id="sel-sr">-</div><div class="l">success rate</div></div>
     <div class="metric"><div class="v" id="sel-checks">-</div><div class="l">checks</div></div>
   </div>
   <button onclick="recheckProxy()" style="margin-top:6px;font-size:11px">recheck</button>
   <button onclick="proxySelect('')" style="margin-top:6px;font-size:11px">clear selection</button>
</div>
</div>

<div class="card">
<h2>client log</h2>
<div class="live" id="proxy-log" style="max-height:200px"><div class="empty small">proxy not started</div></div>
</div>
</div>

<div class="col" style="min-width:540px">

<div class="card">
<h2>select upstream proxy</h2>
<div class="tbl-wrap" style="max-height:500px">
<table>
 <thead><tr>
<th>#</th><th class="sortable" onclick="sortProxy('address')">proxy</th><th class="sortable" onclick="sortProxy('country')">country</th>      <th class="sortable" onclick="sortProxy('last_latency')">latency</th><th class="sortable" onclick="sortProxy('latency_avg')">avg</th><th class="sortable" onclick="sortProxy('speed_avg')" title="KB/s">KB/s</th><th class="sortable" onclick="sortProxy('success_rate')">success</th><th class="sortable" onclick="sortProxy('score')">score</th><th class="sortable" onclick="sortProxy('supports_connect')">flags</th><th class="sortable" onclick="sortProxy('last_ok')" style="width:48px">ok</th><th></th>
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
function ccode(n){var m={};'US=United States|GB=United Kingdom|DE=Germany|FR=France|NL=Netherlands|JP=Japan|CA=Canada|RU=Russia|CN=China|BR=Brazil|ES=Spain|IT=Italy|PL=Poland|UA=Ukraine|IN=India|AU=Australia|SG=Singapore|KR=Korea|MX=Mexico|SE=Sweden|NO=Norway|FI=Finland|CH=Switzerland|HK=Hong Kong'.split('|').forEach(function(x){var p=x.split('=');m[p[1]]=p[0]});return m[n]||''}
function shortCountry(n){return n&&n.length>10?n.substring(0,9)+'\u2026':n}
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
  var geoT=geoTitle(ap);
  var geoHtml='';
  if(ap.listen_country) geoHtml+='server: '+flag(ccode(ap.listen_country))+ap.listen_country+(ap.listen_city?', '+ap.listen_city:'')+(ap.listen_isp?', '+ap.listen_isp:'')+'<br>';
  if(ap.egress_isp) geoHtml+='isp: '+ap.egress_isp+'<br>';
  if(ap.egress_ip) geoHtml+='exit ip: '+ap.egress_ip;
  document.getElementById('sel-geo').innerHTML=geoHtml||'\u2014';
  var badges='<span class="sel-badge sel-country">'+flag(ap.country_code)+' '+ap.country+'</span><span class="sel-badge sel-proto">'+ap.protocol+'</span>';
  document.getElementById('sel-badges').innerHTML=badges;
  document.getElementById('sel-score').textContent=ap.score.toFixed(0);
  document.getElementById('sel-lat').textContent=(ap.last_latency||0).toFixed(2)+'s';
  document.getElementById('sel-speed').textContent=(ap.speed_avg||0).toFixed(0);
  document.getElementById('sel-sr').textContent=(ap.success_rate*100).toFixed(0)+'%';
  document.getElementById('sel-checks').textContent=ap.checks_ok+'/'+ap.checks_total;
}

async function proxySelect(a){
  await api('/api/proxy/select?address='+encodeURIComponent(a||''),'POST');
  if(!a){document.getElementById('selected-card').style.display='none';_selectedAddr=null}
  else{var ps=await api('/api/proxy/status');renderSelected(ps.active_proxy)}
}

async function recheckProxy(){
  if(!_selectedAddr)return;
  var btn=event.target; btn.disabled=true; btn.textContent='checking...';
  var r=await api('/api/proxy/recheck?address='+encodeURIComponent(_selectedAddr),'POST');
  btn.disabled=false; btn.textContent='recheck';
  if(r && r.ok){var ps=await api('/api/proxy/status');renderSelected(ps.active_proxy)}
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
proxyLogLines=s.log.map(function(e){return '<span class="live-ts">'+fmtTime(e.ts)+'</span> '+e.client+' \u2192 '+e.target+' ['+e.status+']'+(e.upstream&&e.upstream!=='direct'&&e.upstream!=='?'?' <span style="color:#8250df">via '+e.upstream+'</span>':'')});
pl.innerHTML=proxyLogLines.join('<br>');
} else if(!s.running) {pl.innerHTML='<div class="empty small">proxy not started</div>'}
}

function ago(ts){if(!ts)return '\u2014';var d=Date.now()/1000-ts;if(d<60)return Math.floor(d)+'s';if(d<3600)return Math.floor(d/60)+'m';if(d<86400)return Math.floor(d/3600)+'h';return Math.floor(d/86400)+'d'}
function geoTitle(p){var a=[],nl='\n';if(p.egress_isp)a.push('isp: '+p.egress_isp);if(p.listen_country)a.push('server: '+p.listen_country+(p.listen_city?', '+p.listen_city:'')+(p.listen_isp?', '+p.listen_isp:''));if(p.egress_ip)a.push('exit ip: '+p.egress_ip);return a.join(nl)}
var topSortKey='score',topSortDir=-1,proxySortKey='score',proxySortDir=-1;
function sortTop(k){if(topSortKey===k)topSortDir*=-1;else{topSortKey=k;topSortDir=k==='score'||k==='success_rate'?-1:1};poll()}
function sortProxy(k){if(proxySortKey===k)proxySortDir*=-1;else{proxySortKey=k;proxySortDir=k==='score'||k==='success_rate'?-1:1};poll()}
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
var sorted=s.top_proxies.slice().sort(function(a,b){var va=a[topSortKey],vb=b[topSortKey];if(topSortKey==='address'||topSortKey==='country')return topSortDir*va.localeCompare(vb);return topSortDir*(va-vb)});
tb.innerHTML=sorted.length?sorted.map(function(p,i){var sc=Math.min(100,Math.max(0,p.score));var flags=[];if(p.supports_connect)flags.push('<span style="color:#1a7f37;font-weight:600">HTTPS</span>');else flags.push('<span style="color:#656d76">HTTP</span>');if(p.mitm_suspect)flags.push('<span style="color:#cf222e;font-weight:600">MITM!</span>');var proto=p.protocol||'http';return'<tr><td style="color:#656d76">'+(i+1)+'</td><td class="addr">'+p.address+'</td><td>'+flag(p.country_code)+' '+shortCountry(p.country)+(p.listen_country&&p.listen_country!==p.country?' \u2192 '+shortCountry(p.listen_country):'')+'</td><td>'+p.last_latency.toFixed(2)+'s</td><td>'+(p.latency_avg.toFixed(2))+'s</td><td>'+(p.speed_avg||0).toFixed(0)+'</td><td>'+(p.success_rate*100).toFixed(0)+'%</td><td>'+p.checks_ok+'/'+p.checks_total+'</td><td><div class="score-bar"><div class="s" style="width:'+sc+'%"></div></div></td><td style="font-size:11px"><span style="color:#8250df">'+proto+'</span> '+flags.join(' ')+'</td><td style="font-size:11px;white-space:nowrap">'+ago(p.last_ok)+'</td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+p.address+'\')">bl</button></td></tr>'}).join(''):'<tr><td colspan="12" class="empty">no alive proxies</td></tr>';

// blacklist
var bb=document.getElementById('bl-body');
bb.innerHTML=s.blacklist.length?s.blacklist.map(function(b){return'<tr><td class="addr">'+b.address+'</td><td style="color:#8250df">'+(b.reason||'\u2014')+'</td><td>'+(b.country||'\u2014')+'</td><td><button class="danger" style="padding:2px 6px;font-size:10px" onclick="blRemove(\''+b.address+'\')">\u00d7</button></td></tr>'}).join(''):'<tr><td colspan="4" class="empty">no entries</td></tr>';
}

function renderProxyList(alive){
var tb=document.getElementById('proxy-list-body');
var sorted=alive.slice().sort(function(a,b){var va=a[proxySortKey],vb=b[proxySortKey];if(proxySortKey==='address'||proxySortKey==='country')return proxySortDir*va.localeCompare(vb);return proxySortDir*(va-vb)});
tb.innerHTML=sorted.length?sorted.map(function(p,i){var sc=Math.min(100,Math.max(0,p.score));var flags=[];if(p.supports_connect)flags.push('<span style="color:#1a7f37;font-weight:600">HTTPS</span>');else flags.push('<span style="color:#656d76">HTTP</span>');if(p.mitm_suspect)flags.push('<span style="color:#cf222e;font-weight:600">MITM!</span>');var proto=p.protocol||'http';return'<tr><td style="color:#656d76">'+(i+1)+'</td><td class="addr">'+p.address+'</td><td>'+flag(p.country_code)+' '+shortCountry(p.country)+(p.listen_country&&p.listen_country!==p.country?' \u2192 '+shortCountry(p.listen_country):'')+'</td><td>'+p.last_latency.toFixed(2)+'s</td><td>'+(p.latency_avg.toFixed(2))+'s</td><td>'+(p.speed_avg||0).toFixed(0)+'</td><td>'+(p.success_rate*100).toFixed(0)+'%</td><td><div class="score-bar"><div class="s" style="width:'+sc+'%"></div></div></td><td style="font-size:11px"><span style="color:#8250df">'+proto+'</span> '+flags.join(' ')+'</td><td style="font-size:11px;white-space:nowrap">'+ago(p.last_ok)+'</td><td><button style="padding:3px 8px;font-size:11px" onclick="proxySelect(\''+p.address+'\')">select</button></td></tr>'}).join(''):'<tr><td colspan="11" class="empty">no proxies available</td></tr>';
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
        self.proxy = ProxyRunner(state, host)
        self._server: Optional[asyncio.AbstractServer] = None
        if hasattr(state, '_proxy_direct_mode'):
            self.proxy.direct_mode = state._proxy_direct_mode
        if hasattr(state, '_proxy_active_addr') and state._proxy_active_addr:
            self.proxy.active_proxy_addr = state._proxy_active_addr

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

    def _serve_static(self, path: str):
        if not WEB_DIR.exists():
            return None
        safe = path.lstrip("/")
        if ".." in safe or safe.startswith("/"):
            return None
        target = WEB_DIR / safe
        try:
            target.resolve().relative_to(WEB_DIR.resolve())
        except ValueError:
            return None
        if not target.exists() or not target.is_file():
            return None
        data = target.read_bytes()
        ext = target.suffix.lower()
        ct = STATIC_MIME.get(ext, "application/octet-stream")
        return data, 200, ct

    async def _route(self, method, path, body):
        if path.startswith("/css/") or path.startswith("/js/") or path.startswith("/img/") or path.startswith("/assets/"):
            static = self._serve_static(path)
            if static:
                return static

        if path == "/legacy":
            return WEB_HTML, 200, "text/html; charset=utf-8"

        if path == "/" or path.startswith("/index"):
            if WEB_DIR.exists() and (WEB_DIR / "index.html").exists():
                return self._serve_static("index.html")
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
            self.state._proxy_active_addr = self.proxy.active_proxy_addr
            self.state._proxy_direct_mode = self.proxy.direct_mode
            self.state._save_state()
            return json.dumps({"ok": True, "address": address}), 200, "application/json"

        if path == "/api/proxy/next":
            alive = [r for r in self.state.ratings.values()
                     if r.last_status == "ok" and not r.in_blacklist]
            alive.sort(key=lambda r: r.score, reverse=True)
            current = self.proxy.active_proxy_addr
            next_proxy = None
            for r in alive:
                if r.address != current:
                    next_proxy = r
                    break
            if next_proxy:
                self.proxy.select(next_proxy.address)
                self.state._proxy_active_addr = self.proxy.active_proxy_addr
                self.state._save_state()
                return json.dumps({"ok": True, "address": next_proxy.address}), 200, "application/json"
            return json.dumps({"ok": False, "error": "no other alive proxy"}), 200, "application/json"

        if path.startswith("/api/proxy/recheck"):
            qs = _qs(path)
            address = qs.get("address", "").strip()
            if address:
                host, port_str = address.rsplit(":", 1)
                port = int(port_str)
                is_socks = port in (1080, 10808, 9050, 4145)
                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency = await self.state._check_proxy(address)
                speed = 0.0
                if ok:
                    try:
                        speed = await self.state._measure_speed(host, port, is_socks)
                    except Exception:
                        speed = 0.0
                self.state._update_rating(address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed)
                self.state._save_state()
                self.state._save_working_file()
                return json.dumps({"ok": ok, "address": address}), 200, "application/json"
            return json.dumps({"ok": False, "error": "no address"}), 400, "application/json"

        if path.startswith("/api/proxy/direct"):
            qs = _qs(path)
            en = qs.get("on", "true").lower() != "false"
            self.proxy.direct_mode = en
            if en:
                self.proxy.active_proxy_addr = None
            self.state._proxy_direct_mode = en
            self.state._proxy_active_addr = self.proxy.active_proxy_addr
            self.state._emit(f"Direct mode: {'ON' if en else 'OFF'}", "info")
            self.state._save_state()
            return json.dumps({"ok": True, "direct_mode": en}), 200, "application/json"

        if path.startswith("/api/settings/country_filter") and method == "POST":
            qs = _qs(path)
            code = qs.get("code", "").upper()
            self.state.country_filter = code
            self.state._emit(f"Country filter set to: {code or 'ALL'}", "info")
            return json.dumps({"ok": True, "country_filter": self.state.country_filter}), 200, "application/json"

        # === Overview / Dashboard endpoints ===
        if path == "/api/countries":
            return json.dumps(self.state.get_countries()), 200, "application/json"

        if path.startswith("/api/system"):
            return json.dumps(self.state._get_system()), 200, "application/json"

        if path.startswith("/api/activity"):
            qs = _qs(path)
            limit = int(qs.get("limit", 10))
            return json.dumps(self.state.get_activity(limit)), 200, "application/json"

        if path.startswith("/api/history"):
            qs = _qs(path)
            last = qs.get("last", "1h")
            return json.dumps(self.state.get_history(last)), 200, "application/json"

        # === Proxies ===
        if path.startswith("/api/proxies"):
            qs = _qs(path)
            status = qs.get("status", "")
            page = int(qs.get("page", 1))
            limit = int(qs.get("limit", 20))
            all_proxies = list(self.state.ratings.values())
            if status == "alive":
                all_proxies = [r for r in all_proxies if r.last_status == "ok" and not r.in_blacklist]
            elif status == "dead":
                all_proxies = [r for r in all_proxies if r.last_status == "failed"]
            elif status == "blacklisted":
                all_proxies = [r for r in all_proxies if r.in_blacklist]
            total = len(all_proxies)
            start = (page - 1) * limit
            end = start + limit
            page_data = all_proxies[start:end]
            return json.dumps({
                "total": total,
                "page": page,
                "limit": limit,
                "proxies": [r.to_dict() for r in page_data],
            }), 200, "application/json"

        if path.startswith("/api/proxy/") and method == "GET":
            addr = path[len("/api/proxy/"):]
            addr = unquote(addr)
            r = self.state.ratings.get(addr)
            if r:
                return json.dumps(r.to_dict()), 200, "application/json"
            return json.dumps({"error": "not found"}), 404, "application/json"

        # === Blacklist ===
        if path.startswith("/api/blacklist"):
            qs = _qs(path)
            page = int(qs.get("page", 1))
            limit = int(qs.get("limit", 20))
            bl = self.state._blacklist_view()
            total = len(bl)
            start = (page - 1) * limit
            end = start + limit
            return json.dumps({
                "total": total,
                "page": page,
                "limit": limit,
                "blacklist": bl[start:end],
            }), 200, "application/json"

        # === Actions ===
        if path.startswith("/api/clear_dead") and method == "POST":
            dead_addrs = [a for a, r in self.state.ratings.items() if r.last_status == "failed"]
            for a in dead_addrs:
                del self.state.ratings[a]
            self.state._emit(f"Cleared {len(dead_addrs)} dead proxies", "warn")
            self.state._save_state()
            self.state._save_working_file()
            return json.dumps({"ok": True, "cleared": len(dead_addrs)}), 200, "application/json"

        if path.startswith("/api/export") and method == "POST":
            data = self.state.working_file.read_text() if self.state.working_file.exists() else ""
            return json.dumps({"ok": True, "data": data}), 200, "application/json"

        if path.startswith("/api/import") and method == "POST":
            try:
                data = json.loads(body or b"{}")
                lines = data.get("proxies", [])
                added = 0
                for line in lines:
                    addr = line.strip()
                    if not addr or ":" not in addr:
                        continue
                    if addr not in self.state.ratings and addr not in self.state.blacklist:
                        self.state.ratings[addr] = ProxyRating(address=addr, first_seen=time.time(), last_check=time.time(), checks_total=1, checks_ok=1, last_status="ok")
                        added += 1
                self.state._emit(f"Imported {added} proxies", "info")
                self.state._save_state()
                self.state._save_working_file()
                return json.dumps({"ok": True, "added": added}), 200, "application/json"
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

        if path.startswith("/api/health/start") and method == "POST":
            try:
                asyncio.create_task(self.state._health_check())
                return json.dumps({"ok": True}), 200, "application/json"
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"

        # === Settings ===
        if path.startswith("/api/settings") and method == "GET":
            if not CONFIG_PATH.exists():
                return json.dumps({"error": "config not found"}), 404, "application/json"
            with open(CONFIG_PATH) as f:
                cfg = yaml.safe_load(f)
            return json.dumps(cfg or {}), 200, "application/json"

        if path.startswith("/api/settings") and method == "POST":
            try:
                data = json.loads(body or b"{}")
                with open(CONFIG_PATH, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                self.state._emit("Settings updated", "info")
                return json.dumps({"ok": True}), 200, "application/json"
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

        # === Logs ===
        if path.startswith("/api/logs"):
            qs = _qs(path)
            limit = int(qs.get("limit", 50))
            log_file = DATA_DIR / "huntproxy.log"
            lines = []
            if log_file.exists():
                try:
                    with open(log_file) as f:
                        lines = f.readlines()[-limit:]
                except Exception:
                    pass
            return json.dumps({"lines": [l.rstrip() for l in lines]}), 200, "application/json"

        # === Downloads ===
        if path.startswith("/api/download/"):
            filename = path[len("/api/download/"):]
            filename = unquote(filename)
            if filename not in ("working.txt", "blacklist.txt", "ratings.json", "config.yaml"):
                return json.dumps({"error": "forbidden"}), 403, "application/json"
            target = DATA_DIR / filename if filename != "config.yaml" else CONFIG_PATH
            if not target.exists():
                return json.dumps({"error": "not found"}), 404, "application/json"
            data = target.read_bytes()
            ct = "application/octet-stream"
            if filename.endswith(".txt"):
                ct = "text/plain; charset=utf-8"
            elif filename.endswith(".json"):
                ct = "application/json"
            elif filename.endswith(".yaml"):
                ct = "text/yaml"
            return data, 200, ct

        # === Proxy Control / Traffic stubs (Phase 2) ===
        if path.startswith("/api/traffic"):
            return json.dumps({"points": self.state.get_history("24h")}), 200, "application/json"

        if path.startswith("/api/requests"):
            mem = list(self.proxy.log)[-50:]
            try:
                conn = self.state._db()
                rows = conn.execute("SELECT ts, client, target, status, upstream, bytes_in, bytes_out, duration FROM traffic_log ORDER BY id DESC LIMIT 50").fetchall()
                conn.close()
                db_reqs = [dict(r) for r in rows]
            except Exception:
                db_reqs = []
            reqs = db_reqs if db_reqs else mem
            return json.dumps({"requests": reqs}), 200, "application/json"

        if path.startswith("/api/clients"):
            clients = {}
            try:
                conn = self.state._db()
                rows = conn.execute("SELECT client, COUNT(*) as requests, MAX(ts) as last_seen FROM traffic_log GROUP BY client ORDER BY requests DESC LIMIT 20").fetchall()
                conn.close()
                for r in rows:
                    clients[r["client"]] = {"client": r["client"], "requests": r["requests"], "last_seen": r["last_seen"]}
            except Exception:
                for entry in self.proxy.log:
                    c = entry.get("client", "?")
                    if c not in clients:
                        clients[c] = {"client": c, "requests": 0, "last_seen": entry.get("ts", 0)}
                    clients[c]["requests"] += 1
                    clients[c]["last_seen"] = max(clients[c]["last_seen"], entry.get("ts", 0))
            return json.dumps({"clients": sorted(clients.values(), key=lambda x: x["requests"], reverse=True)[:20]}), 200, "application/json"

        if path.startswith("/api/domains"):
            domains = {}
            try:
                conn = self.state._db()
                rows = conn.execute("SELECT target, COUNT(*) as requests FROM traffic_log WHERE client != '?' GROUP BY target ORDER BY requests DESC LIMIT 50").fetchall()
                conn.close()
                for r in rows:
                    t = r["target"]
                    try:
                        h = urlparse(t if t.startswith("http") else f"http://{t}").hostname or t
                    except Exception:
                        h = t
                    if not h:
                        continue
                    if h not in domains:
                        domains[h] = {"domain": h, "requests": 0}
                    domains[h]["requests"] += r["requests"]
            except Exception:
                for entry in self.proxy.log:
                    t = entry.get("target", "")
                    try:
                        h = urlparse(t if t.startswith("http") else f"http://{t}").hostname or t
                    except Exception:
                        h = t
                    if not h:
                        continue
                    if h not in domains:
                        domains[h] = {"domain": h, "requests": 0}
                    domains[h]["requests"] += 1
            top = sorted(domains.values(), key=lambda x: x["requests"], reverse=True)[:10]
            total = sum(d["requests"] for d in top) or 1
            for d in top:
                d["pct"] = round(d["requests"] / total * 100, 1)
            return json.dumps({"domains": top}), 200, "application/json"

        if path.startswith("/api/errors"):
            errors = {"timeout": 0, "connect_failed": 0, "4xx": 0, "5xx": 0, "other": 0}
            try:
                conn = self.state._db()
                rows = conn.execute("SELECT status, COUNT(*) as cnt FROM traffic_log WHERE status != 'ok' GROUP BY status").fetchall()
                conn.close()
                for r in rows:
                    st = r["status"]
                    cnt = r["cnt"]
                    if "timeout" in st.lower():
                        errors["timeout"] += cnt
                    elif "connect" in st.lower() or "fail" in st.lower():
                        errors["connect_failed"] += cnt
                    elif st.startswith("4"):
                        errors["4xx"] += cnt
                    elif st.startswith("5") or st.startswith("502") or st.startswith("503"):
                        errors["5xx"] += cnt
                    else:
                        errors["other"] += cnt
            except Exception:
                for entry in self.proxy.log:
                    st = entry.get("status", "")
                    if "timeout" in st.lower():
                        errors["timeout"] += 1
                    elif "connect" in st.lower() or "fail" in st.lower():
                        errors["connect_failed"] += 1
                    elif st.startswith("4"):
                        errors["4xx"] += 1
                    elif st.startswith("5") or st.startswith("502") or st.startswith("503"):
                        errors["5xx"] += 1
                    else:
                        errors["other"] += 1
            total = sum(errors.values()) or 1
            result = []
            for k, v in errors.items():
                if v:
                    result.append({"type": k, "count": v, "pct": round(v / total * 100, 1)})
            return json.dumps({"errors": result, "total": total}), 200, "application/json"

        if path.startswith("/api/bandwidth"):
            try:
                conn = self.state._db()
                row = conn.execute(
                    "SELECT COALESCE(SUM(bytes_in),0) as incoming, COALESCE(SUM(bytes_out),0) as outgoing "
                    "FROM traffic_log WHERE ts > ?",
                    (time.time() - 86400,)
                ).fetchone()
                conn.close()
                incoming = row["incoming"] if row else 0
                outgoing = row["outgoing"] if row else 0
            except Exception:
                incoming = 0
                outgoing = 0
            return json.dumps({
                "incoming": incoming,
                "outgoing": outgoing,
                "incoming_gb": round(incoming / (1024**3), 3),
                "outgoing_gb": round(outgoing / (1024**3), 3),
            }), 200, "application/json"

        return json.dumps({"error": "not found"}), 404, "application/json"


def setup_logging():
    level = os.environ.get("HUNTPROXY_LOG_LEVEL", "INFO")
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")


async def amain(config: dict):
    hunt_cfg = config.get("hunt", {})
    host = hunt_cfg.get("web_listen_host", "127.0.0.1")
    port = hunt_cfg.get("web_listen_port", 17177)

    state = HuntState(hunt_cfg)
    server = HuntServer(state, host, port)
    state.proxy_runner = server.proxy

    # Start periodic history recording (every 60s)
    asyncio.create_task(state._history_loop())

    print("=" * 56)
    print(f"  huntproxy HUNT — web UI: http://{host}:{port}/")
    print(f"  data dir: {DATA_DIR}")
    print("  Ctrl+C to stop")
    print("=" * 56)

    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    finally:
        state._save_state()
        state._save_working_file()
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
