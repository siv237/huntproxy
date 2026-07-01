"""Functional split of the huntproxy backend."""

import asyncio
import ipaddress
import time
from hunt.blacklist import BlacklistMixin
from hunt.favorites import FavoritesMixin
from hunt.actions import ActionsMixin
from hunt.backup import BackupMixin
from hunt.blocklists import BlocklistsMixin
from hunt.channel import ChannelMixin
from hunt.check_validation import CheckValidationMixin
from hunt.check_proxy import CheckProxyMixin
from hunt.check_ssl import CheckSslMixin
from hunt.check_speed import CheckSpeedMixin
from hunt.check_mitm import CheckMitmMixin
import logging

logger = logging.getLogger(__name__)
from hunt.check_geo import CheckGeoMixin
from hunt.check_rating import CheckRatingMixin
from hunt.state_persistence import StatePersistenceMixin
from hunt.state_download import StateDownloadMixin
from hunt.constants import DATA_DIR, logger
from hunt.custom_proxies import CustomProxiesMixin
from hunt.db import DbMixin
from hunt.events import EventsMixin
from hunt.hunt_control import HuntControlMixin
from hunt.hunt_cycle import HuntCycleMixin
from hunt.canary import CanaryMixin
from hunt.health_loops import HealthLoopsMixin
from hunt.health_check import HealthCheckMixin
from hunt.ip_blacklist import IPBlacklistMixin
from hunt.ip_blacklist_sources import IPBlacklistSourcesMixin
from hunt.models import ProxyRating
from hunt.proxy_sources import ProxySourcesMixin
from hunt.routing import RoutingMixin
from hunt.snapshot import SnapshotMixin
from pathlib import Path
from typing import Optional

class HuntState(DbMixin, EventsMixin, SnapshotMixin, HuntControlMixin, HuntCycleMixin, CanaryMixin, HealthLoopsMixin, HealthCheckMixin, CheckValidationMixin, CheckProxyMixin, CheckSslMixin, CheckSpeedMixin, CheckMitmMixin, CheckGeoMixin, CheckRatingMixin, BlacklistMixin, IPBlacklistMixin, ProxySourcesMixin, IPBlacklistSourcesMixin, BlocklistsMixin, RoutingMixin, CustomProxiesMixin, ChannelMixin, ActionsMixin, BackupMixin, FavoritesMixin, StatePersistenceMixin, StateDownloadMixin):
    PHASE_IDLE = "idle"

    PHASE_DOWNLOAD = "downloading"

    PHASE_BLACKLIST = "blacklists"

    PHASE_VALIDATE = "validating"

    PHASE_HEALTH = "health"

    PHASE_DONE = "done"

    PHASE_PAUSED = "paused"

    def __init__(self, config: dict):
            self.config = config
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.ratings: dict[str, ProxyRating] = {}
            self.blacklist: dict[str, str] = {}
            self.favorites: set[str] = set()
            self._geo_cache: dict[str, dict] = {}

            # IP blacklist (downloaded lists of banned exit IPs / CIDRs)
            self.ip_blacklist_entries: dict[str, list[dict]] = {}  # ip/cidr -> [{source_id, source_name, reason}, ...]
            self.ip_blacklist_exact: set[str] = set()
            self.ip_blacklist_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
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
            self._health_manual: bool = False
            self._health_task: Optional[asyncio.Task] = None

            # Reference to the startup-cycle background task, held so the GC
            # does not destroy it mid-cycle (see main.py / run_startup_cycle).
            self._startup_task: Optional[asyncio.Task] = None
            # Service state for restoration after restart
            self._hunt_running: bool = False
            self._proxy_running: bool = False
            self._proxy_port: int = 17277
            self._socks5_running: bool = False
            self._socks5_port: int = 17278
            self._transparent_running: bool = False
            self._transparent_port: int = 17477
            self._proxy_direct_mode: bool = False
            self._proxy_active_addr: Optional[str] = None
            # Chronology of upstream proxy switches (select/clear/direct),
            # persisted in runtime_state so it survives restarts.
            self._proxy_switch_history: list[dict] = []
            # Channel proxy: routes the engine's own internet access through an
            # upstream proxy ("" / "direct" / "proxy:<addr>" / "custom:<id>").
            self._channel_route: str = ""

            # Persistence batching counter
            self._rating_updates_since_save: int = 0
            # Track which ratings changed since the last full save so the
            # periodic save can upsert only those rows instead of rewriting
            # the entire ratings table on every batch.
            self._dirty_ratings: set[str] = set()

            # Seed psutil's CPU baseline so the first dashboard snapshot
            # reports a real value instead of 0.0 (cpu_percent needs two
            # samples to compute a delta).
            try:
                import psutil
                psutil.cpu_percent(interval=None)
            except Exception:
                logger.debug("suppressed", exc_info=True)

            # Hunt progress counters
            self.sources_total: int = 0
            self.sources_done: int = 0
            self.downloaded: int = 0
            self.bl_sources_total: int = 0
            self.bl_sources_done: int = 0
            self.bl_results: list = []
            self._source_fetch_status: dict = {}
            self.checked: int = 0
            self.checking_total: int = 0
            self.working: int = 0
            self.new_working: int = 0
            self.confirmed_working: int = 0
            self.failed: int = 0
            # Skip control: lets the operator abort the current download or
            # validation phase and continue with what has been collected so far.
            self._skip_requested: bool = False
            self._skip_event: asyncio.Event = asyncio.Event()
            self._active_dl_procs: list = []
            self.last_event: str = ""
            self.last_proxy: Optional[str] = None
            self.last_country: str = ""
            self._source_proxies: dict[str, set] = {}
            self._addr_sources: dict[str, list] = {}
            self.events: list[dict] = []
            self._event_seq = 0
            self._cond = asyncio.Condition()
            self._active_checks: dict[str, dict] = {}

            # settings
            cfg = config.get("hunt", {})
            self.parallel = cfg.get("parallel", 30)
            self.timeout = cfg.get("timeout", 8)
            self._base_timeout = self.timeout
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

            # Scheduler (set by main.py after construction)
            self.scheduler = None

            self.started_at = time.time()
            self._db_path = DATA_DIR / "stats.db"
            self._state_db_path = DATA_DIR / "state.db"
            self._last_history_ts = time.time()
            self._init_db()
            self._seed_default_sources()
            self._migrate_sources()
            self._seed_default_ip_blacklist_sources()
            self._migrate_ip_blacklist_sources()
            self._seed_default_blocklists()
            self._migrate_blocklists()
            try:
                conn = self._stats_db()
                row = conn.execute("SELECT MAX(ts) as last_ts FROM history").fetchone()
                conn.close()
                if row and row["last_ts"]:
                    self._last_history_ts = row["last_ts"]
            except Exception:
                logger.debug("suppressed", exc_info=True)
            self._load_ip_blacklist()
            self._load_state()
            self._load_working_file()
            self._load_all_proxy_source_entries()
            try:
                self._channel_route = self._routing_get("channel_route", "")
            except Exception:
                logger.debug("suppressed", exc_info=True)

    @property
    def working_file(self) -> Path:
            return DATA_DIR / "working.txt"

    SPEED_SERVERS = [
            ("speedtest.tele2.net", "/512KB.zip", 524288),
            ("speedtest.tele2.net", "/1MB.zip", 1048576),
            ("cachefly.cachefly.net", "/1mb.test", 1048576),
        ]

