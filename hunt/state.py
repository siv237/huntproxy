"""Functional split of the huntproxy backend."""

import asyncio
import ipaddress
import json
import time
from hunt.blacklist import BlacklistMixin
from hunt.actions import ActionsMixin
from hunt.checking import CheckingMixin
from hunt.constants import DATA_DIR, logger
from hunt.custom_proxies import CustomProxiesMixin
from hunt.db import DbMixin
from hunt.events import EventsMixin
from hunt.geo import country_code_from_name
from hunt.health import HealthMixin
from hunt.ip_blacklist import IPBlacklistMixin
from hunt.ip_blacklist_sources import IPBlacklistSourcesMixin
from hunt.models import ProxyRating
from hunt.proxy_sources import ProxySourcesMixin
from hunt.routing import RoutingMixin
from hunt.snapshot import SnapshotMixin
from pathlib import Path
from typing import Optional

class HuntState(DbMixin, EventsMixin, SnapshotMixin, HealthMixin, CheckingMixin, BlacklistMixin, IPBlacklistMixin, ProxySourcesMixin, IPBlacklistSourcesMixin, RoutingMixin, CustomProxiesMixin, ActionsMixin):
    PHASE_IDLE = "idle"

    PHASE_DOWNLOAD = "downloading"

    PHASE_VALIDATE = "validating"

    PHASE_HEALTH = "health"

    PHASE_DONE = "done"

    PHASE_PAUSED = "paused"

    def __init__(self, config: dict):
            self.config = config
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.ratings: dict[str, ProxyRating] = {}
            self.blacklist: dict[str, str] = {}
            self._geo_cache: dict[str, dict] = {}

            # IP blacklist (downloaded lists of banned exit IPs / CIDRs)
            self.ip_blacklist_entries: dict[str, list[dict]] = {}  # ip/cidr -> [{source_id, source_name, reason}, ...]
            self.ip_blacklist_exact: set[str] = set()
            self.ip_blacklist_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
            self.ip_blacklist_file: Path = DATA_DIR / "ip_blacklist.txt"
            self._fetching_ip_blacklists: bool = False
            self.phase: str = self.PHASE_IDLE
            self.phase_started: float = 0.0
            self.task: Optional[asyncio.Task] = None

            self._paused: bool = False
            self._manual_pause: bool = False
            self._pause_event: asyncio.Event = asyncio.Event()
            self._pause_event.set()
            self._phase_before_pause: str = self.PHASE_DONE
            self._internet_suspect: bool = False
            self._fail_streak: int = 0
            self._check_streak: int = 0
            self._canary_task: Optional[asyncio.Task] = None
            self._health_running: bool = False

            # Service state for restoration after restart
            self._hunt_running: bool = False
            self._proxy_running: bool = False
            self._proxy_port: int = 17277
            self._socks5_running: bool = False
            self._socks5_port: int = 17278
            self._proxy_direct_mode: bool = False
            self._proxy_active_addr: Optional[str] = None

            # Persistence batching counter
            self._rating_updates_since_save: int = 0

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
            self._source_proxies: dict[str, set] = {}
            self._addr_sources: dict[str, list] = {}
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

            self.canary_hosts = cfg.get("canary_hosts", ["ya.ru", "google.com", "2ip.ru"])
            self._canary_last_check: float = 0
            self._canary_interval: float = 30
            self._internet_alive: Optional[bool] = None
            self._canary_cache: dict = {}

            # IP blacklist settings
            ip_bl_cfg = config.get("ip_blacklists", {})
            self.ip_blacklist_enabled = ip_bl_cfg.get("enabled", True)
            self.ip_blacklist_fetch_interval = ip_bl_cfg.get("fetch_interval", 3600)

            self.started_at = time.time()
            self._db_path = DATA_DIR / "stats.db"
            self._state_db_path = DATA_DIR / "state.db"
            self._last_history_ts = time.time()
            self._init_db()
            self._seed_default_sources()
            self._migrate_sources()
            self._seed_default_ip_blacklist_sources()
            self._migrate_ip_blacklist_sources()
            try:
                conn = self._stats_db()
                row = conn.execute("SELECT MAX(ts) as last_ts FROM history").fetchone()
                conn.close()
                if row and row["last_ts"]:
                    self._last_history_ts = row["last_ts"]
            except Exception:
                pass
            self._load_ip_blacklist()
            self._load_state()
            self._load_all_proxy_source_entries()
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

    SPEED_SERVERS = [
            ("speedtest.tele2.net", "/512KB.zip", 524288),
            ("speedtest.tele2.net", "/1MB.zip", 1048576),
            ("cachefly.cachefly.net", "/1mb.test", 1048576),
        ]

    def _load_state(self):
            # SQLite is the primary state store; legacy files are fallback-only.
            try:
                conn = self._db()
                # ratings
                self.ratings.clear()
                for row in conn.execute("SELECT address, data FROM ratings"):
                    try:
                        d = json.loads(row["data"])
                    except Exception:
                        continue
                    checks_ok = d.get("checks_ok", 0)
                    stored_avg = d.get("latency_avg", 0)
                    last_latency = d.get("last_latency", 0)
                    latency_sum = d.get("latency_sum", stored_avg * checks_ok)
                    latency_count = d.get("latency_count", checks_ok)
                    if latency_count:
                        if abs(latency_sum / latency_count - stored_avg) > 0.001:
                            latency_sum = stored_avg * latency_count
                        if stored_avg == 0 and last_latency > 0:
                            latency_sum = last_latency * latency_count
                    r = ProxyRating(
                        address=d["address"],
                        country=d.get("country", ""),
                        country_code=d.get("country_code", ""),
                        protocol=d.get("protocol", "http"),
                        latency_sum=latency_sum,
                        latency_count=latency_count,
                        last_latency=last_latency,
                        checks_total=d.get("checks_total", 0),
                        checks_ok=checks_ok,
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
                        egress_country_code=d.get("egress_country_code", ""),
                        listen_country=d.get("listen_country", ""),
                        listen_country_code=d.get("listen_country_code", ""),
                        listen_city=d.get("listen_city", ""),
                        listen_isp=d.get("listen_isp", ""),
                        source_ids=d.get("source_ids", []),
                        ssl_supported=d.get("ssl_supported", False),
                        ip_blacklist_reason=d.get("ip_blacklist_reason", ""),
                        ip_blacklist_hits=d.get("ip_blacklist_hits", 0),
                        ip_blacklist_sources=d.get("ip_blacklist_sources", []),
                        in_blacklist=d.get("in_blacklist", False),
                        blacklist_reason=d.get("blacklist_reason", ""),
                    )
                    if not r.egress_country_code and r.egress_country:
                        r.egress_country_code = country_code_from_name(r.egress_country)
                    if not r.listen_country_code and r.listen_country:
                        r.listen_country_code = country_code_from_name(r.listen_country)
                    self.ratings[r.address] = r
                # blacklist
                self.blacklist.clear()
                rows = list(conn.execute("SELECT address, reason FROM blacklist"))
                if rows:
                    for row in rows:
                        self.blacklist[row["address"]] = row["reason"] or ""
                else:
                    self._load_blacklist_file()
                # runtime state
                for row in conn.execute("SELECT key, value FROM runtime_state"):
                    key = row["key"]
                    val = row["value"]
                    if key == "proxy_runner":
                        try:
                            pr = json.loads(val)
                            self._proxy_direct_mode = pr.get("direct_mode", False)
                            self._proxy_active_addr = pr.get("active_proxy_addr")
                            self._socks5_port = pr.get("socks5_port", 17278)
                        except Exception:
                            pass
                    elif key == "services":
                        try:
                            services = json.loads(val)
                            self._hunt_running = services.get("hunt_running", False)
                            self._proxy_running = services.get("proxy_running", False)
                            self._proxy_port = services.get("proxy_port", 17277)
                            self._socks5_running = services.get("socks5_running", False)
                            self._socks5_port = services.get("socks5_port", 17278)
                        except Exception:
                            pass
                    elif key == "country_filter":
                        self.country_filter = val
                conn.close()
                self._addr_sources = {}
                for r in self.ratings.values():
                    for sid in r.source_ids:
                        if r.address not in self._addr_sources:
                            self._addr_sources[r.address] = []
                        self._addr_sources[r.address].append(sid)
                if self.ratings:
                    logger.info(f"Loaded {len(self.ratings)} ratings from SQLite")
                    return
            except Exception as e:
                logger.warning(f"SQLite state load failed: {e}")

            # Fallback to legacy ratings.json
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
                    self._socks5_port = pr.get("socks5_port", 17278)
                    services = data.get("services", {})
                    self._hunt_running = services.get("hunt_running", False)
                    self._proxy_running = services.get("proxy_running", False)
                    self._proxy_port = services.get("proxy_port", 17277)
                    self._socks5_running = services.get("socks5_running", False)
                    self._socks5_port = services.get("socks5_port", 17278)
                elif isinstance(data, list):
                    proxies = data
                else:
                    return
                for d in proxies:
                    checks_ok = d.get("checks_ok", 0)
                    stored_avg = d.get("latency_avg", 0)
                    last_latency = d.get("last_latency", 0)
                    latency_sum = d.get("latency_sum", stored_avg * checks_ok)
                    latency_count = d.get("latency_count", checks_ok)
                    if latency_count:
                        if abs(latency_sum / latency_count - stored_avg) > 0.001:
                            latency_sum = stored_avg * latency_count
                        if stored_avg == 0 and last_latency > 0:
                            latency_sum = last_latency * latency_count
                    r = ProxyRating(
                        address=d["address"],
                        country=d.get("country", ""),
                        country_code=d.get("country_code", ""),
                        protocol=d.get("protocol", "http"),
                        latency_sum=latency_sum,
                        latency_count=latency_count,
                        last_latency=last_latency,
                        checks_total=d.get("checks_total", 0),
                        checks_ok=checks_ok,
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
                        egress_country_code=d.get("egress_country_code", ""),
                        listen_country=d.get("listen_country", ""),
                        listen_country_code=d.get("listen_country_code", ""),
                        listen_city=d.get("listen_city", ""),
                        listen_isp=d.get("listen_isp", ""),
                        source_ids=d.get("source_ids", []),
                        ssl_supported=d.get("ssl_supported", False),
                        ip_blacklist_reason=d.get("ip_blacklist_reason", ""),
                        ip_blacklist_hits=d.get("ip_blacklist_hits", 0),
                        ip_blacklist_sources=d.get("ip_blacklist_sources", []),
                        in_blacklist=d.get("in_blacklist", False),
                        blacklist_reason=d.get("blacklist_reason", ""),
                    )
                    if not r.egress_country_code and r.egress_country:
                        r.egress_country_code = country_code_from_name(r.egress_country)
                    if not r.listen_country_code and r.listen_country:
                        r.listen_country_code = country_code_from_name(r.listen_country)
                    self.ratings[r.address] = r
                self._load_blacklist_file()
                self._addr_sources = {}
                for r in self.ratings.values():
                    for sid in r.source_ids:
                        if r.address not in self._addr_sources:
                            self._addr_sources[r.address] = []
                        self._addr_sources[r.address].append(sid)
                logger.info(f"Loaded {len(self.ratings)} ratings from state file")
            except Exception as e:
                logger.warning(f"State load failed: {e}")

    def _save_state(self):
            try:
                conn = self._db()
                # ratings
                conn.execute("DELETE FROM ratings")
                for r in self.ratings.values():
                    conn.execute(
                        "INSERT INTO ratings (address, data) VALUES (?, ?)",
                        (r.address, json.dumps(r.to_dict())),
                    )
                # blacklist
                conn.execute("DELETE FROM blacklist")
                for addr, reason in self.blacklist.items():
                    conn.execute(
                        "INSERT INTO blacklist (address, reason) VALUES (?, ?)",
                        (addr, reason or ""),
                    )
                # runtime state
                conn.execute("DELETE FROM runtime_state")
                runtime = [
                    ("proxy_runner", json.dumps({
                        "direct_mode": getattr(self, '_proxy_direct_mode', False),
                        "active_proxy_addr": getattr(self, '_proxy_active_addr', None),
                        "socks5_port": getattr(self, '_socks5_port', 17278),
                    })),
                    ("services", json.dumps({
                        "hunt_running": getattr(self, '_hunt_running', False),
                        "proxy_running": getattr(self, '_proxy_running', False),
                        "proxy_port": getattr(self, '_proxy_port', 17277),
                        "socks5_running": getattr(self, '_socks5_running', False),
                        "socks5_port": getattr(self, '_socks5_port', 17278),
                    })),
                    ("country_filter", self.country_filter or ""),
                ]
                for key, value in runtime:
                    conn.execute(
                        "INSERT INTO runtime_state (key, value) VALUES (?, ?)",
                        (key, value),
                    )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"SQLite state save failed: {e}")
            # Keep legacy files as human-readable exports
            try:
                data = {
                    "proxies": [r.to_dict() for r in self.ratings.values()],
                    "proxy_runner": {
                        "direct_mode": getattr(self, '_proxy_direct_mode', False),
                        "active_proxy_addr": getattr(self, '_proxy_active_addr', None),
                        "socks5_port": getattr(self, '_socks5_port', 17278),
                    },
                    "services": {
                        "hunt_running": getattr(self, '_hunt_running', False),
                        "proxy_running": getattr(self, '_proxy_running', False),
                        "proxy_port": getattr(self, '_proxy_port', 17277),
                        "socks5_running": getattr(self, '_socks5_running', False),
                        "socks5_port": getattr(self, '_socks5_port', 17278),
                    }
                }
                with open(self.state_file, "w") as f:
                    json.dump(data, f, indent=2)
                self._save_blacklist()
            except Exception as e:
                logger.warning(f"Legacy state export failed: {e}")

    def _load_working_file(self):
            if not self.working_file.exists():
                return
            count = 0
            loaded = set()
            file_mtime = self.working_file.stat().st_mtime
            with open(self.working_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    addr = parts[0]
                    lat_str = parts[-1] if len(parts) > 2 else "0"
                    try:
                        float(lat_str)
                    except ValueError:
                        lat_str = "0"
                        country = " ".join(parts[1:]) if len(parts) > 1 else ""
                    else:
                        country = " ".join(parts[1:-1]) if len(parts) > 2 else (parts[1] if len(parts) > 1 else "")
                    if addr in self.ratings or addr in self.blacklist:
                        continue
                    last_latency = 0.0
                    try:
                        last_latency = float(lat_str)
                    except ValueError:
                        pass
                    r = ProxyRating(
                        address=addr,
                        country=country,
                        country_code=country_code_from_name(country),
                        first_seen=time.time(),
                        last_check=time.time(),
                        checks_total=1,
                        checks_ok=1,
                        last_status="ok",
                        last_latency=last_latency,
                        latency_sum=last_latency,
                        latency_count=1,
                    )
                    if addr.rsplit(":", 1)[-1] in ("1080", "10808", "9050"):
                        r.protocol = "socks5"
                    elif addr.rsplit(":", 1)[-1] == "4145":
                        r.protocol = "socks4"
                    self.ratings[addr] = r
                    loaded.add(addr)
                    count += 1
            if loaded:
                self._working_file_loaded = loaded
                self._working_file_mtime = file_mtime
            if count:
                logger.info(f"Loaded {count} proxies from working.txt")

    def _save_working_file(self):
            """Write alive (non-blacklisted) proxies to working.txt, atomic.

            Only the operator-curated manual blacklist is a hard exclusion;
            downloaded IP blacklist matches only lower the score."""
            alive = [r for r in self.ratings.values()
                     if r.last_status == "ok" and not r.in_blacklist]
            alive.sort(key=lambda r: r.score, reverse=True)
            tmp = self.working_file.with_suffix(".tmp")
            with open(tmp, "w") as f:
                for r in alive:
                    f.write(f"{r.address}  {r.country}  {r.last_latency:.3f}\n")
            tmp.rename(self.working_file)
