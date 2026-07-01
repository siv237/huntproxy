"""Schedule entry dataclass, task types, and default schedules — extracted from scheduler.py."""
import json
from dataclasses import dataclass, field
from typing import Any

TASK_TYPES: dict[str, dict[str, Any]] = {
    "proxy_check": {
        "description": "Re-validate all existing proxies (no new collection)",
        "mutex_with": ["health_check"],
        "respect_pause": False,
        "respect_internet": True,
        "busy_flag": "_hunt_running",
    },
    "ip_blacklist": {
        "description": "Download IP blacklist sources",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": True,
        "busy_flag": "_fetching_ip_blacklists",
    },
    "blocklist": {
        "description": "Download country blocklists",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": True,
        "busy_flag": "_fetching_blocklists",
    },
    "health_check": {
        "description": "Re-validate alive proxies",
        "mutex_with": ["proxy_check"],
        "respect_pause": False,
        "respect_internet": True,
    },
    "history": {
        "description": "Record history snapshot + retention cleanup",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": False,
    },
    "clear_dead": {
        "description": "Remove dead proxies from pool",
        "mutex_with": ["proxy_check", "health_check"],
        "respect_pause": False,
        "respect_internet": False,
    },
    "backup": {
        "description": "Create database backup",
        "mutex_with": [],
        "respect_pause": False,
        "respect_internet": False,
    },
}

# Default schedules seeded on first run (when the DB table is empty).
DEFAULT_SCHEDULES: list[dict[str, Any]] = [
    {
        "id": "history",
        "name": "History recording",
        "task_type": "history",
        "enabled": 1,
        "interval_sec": 60,
        "config": "{}",
    },
    {
        "id": "ip_blacklist_refresh",
        "name": "IP blacklist refresh",
        "task_type": "ip_blacklist",
        "enabled": 1,
        "interval_sec": 3600,
        "config": "{}",
    },
    {
        "id": "blocklist_refresh",
        "name": "Country blocklist refresh",
        "task_type": "blocklist",
        "enabled": 1,
        "interval_sec": 3600,
        "config": "{}",
    },
    {
        "id": "health_check",
        "name": "Health check",
        "task_type": "health_check",
        "enabled": 1,
        "interval_sec": 180,
        "config": "{}",
    },
    {
        "id": "proxy_check",
        "name": "Proxy pool check",
        "task_type": "proxy_check",
        "enabled": 1,
        "interval_sec": 1800,
        "config": "{}",
    },
]


@dataclass
class ScheduleEntry:
    id: str
    name: str
    task_type: str
    enabled: bool = True
    interval_sec: int = 3600
    config: dict = field(default_factory=dict)
    last_run: float = 0.0       # timestamp of last START
    last_ok: float = 0.0        # timestamp of last SUCCESSFUL completion
    next_run: float = 0.0       # hint; real trigger is last_ok + interval
    last_status: str = "never"  # 'ok'|'failed'|'running'|'queued'|'skipped'|'never'
    last_duration_s: float = 0.0
    last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type,
            "enabled": self.enabled,
            "interval_sec": self.interval_sec,
            "config": self.config,
            "last_run": self.last_run,
            "last_ok": self.last_ok,
            "next_run": self.next_run,
            "last_status": self.last_status,
            "last_duration_s": self.last_duration_s,
            "last_error": self.last_error,
        }

    @classmethod
    def from_row(cls, row) -> "ScheduleEntry":
        try:
            cfg = json.loads(row["config"] or "{}")
        except Exception:
            cfg = {}
        return cls(
            id=row["id"],
            name=row["name"],
            task_type=row["task_type"],
            enabled=bool(row["enabled"]),
            interval_sec=row["interval_sec"],
            config=cfg,
            last_run=row["last_run"] or 0.0,
            last_ok=row["last_ok"] if "last_ok" in row.keys() else 0.0,
            next_run=row["next_run"] or 0.0,
            last_status=row["last_status"] or "never",
            last_duration_s=row["last_duration_s"] or 0.0,
            last_error=row["last_error"] or "",
        )

    def is_due(self, now: float) -> bool:
        """A task is due when at least interval_sec has passed since its last
        successful completion. On first run (last_ok == 0) use next_run hint."""
        if self.last_ok > 0:
            return now - self.last_ok >= self.interval_sec
        # Never succeeded yet — fall back to next_run hint (or due immediately
        # if next_run is also unset).
        return now >= self.next_run if self.next_run > 0 else True



