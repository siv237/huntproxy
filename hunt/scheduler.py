"""Unified asyncio scheduler for periodic maintenance tasks.

Replaces the ad-hoc ``_history_loop``, ``_ip_blacklist_loop``,
``_blocklist_loop`` and ``_health_loop`` sleep-cycles with a single
configurable, DB-persisted, runtime-editable scheduler.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from hunt.constants import logger


# ── Task type registry ────────────────────────────────────────────────

TASK_TYPES: dict[str, dict[str, Any]] = {
    "hunt_cycle": {
        "description": "Full download → blacklist → validate cycle",
        "mutex_with": ["health_check"],
        "respect_pause": True,
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
        "mutex_with": ["hunt_cycle"],
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
        "mutex_with": ["hunt_cycle", "health_check"],
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
        "id": "hunt_cycle",
        "name": "Hunt cycle",
        "task_type": "hunt_cycle",
        "enabled": 0,
        "interval_sec": 0,
        "config": "{}",
    },
]

# Tick interval: how often the main loop checks for due schedules.
_TICK_INTERVAL = 5  # seconds


@dataclass
class ScheduleEntry:
    id: str
    name: str
    task_type: str
    enabled: bool = True
    interval_sec: int = 3600
    config: dict = field(default_factory=dict)
    last_run: float = 0.0
    next_run: float = 0.0
    last_status: str = "never"  # 'ok'|'failed'|'running'|'skipped'|'never'
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
            next_run=row["next_run"] or 0.0,
            last_status=row["last_status"] or "never",
            last_duration_s=row["last_duration_s"] or 0.0,
            last_error=row["last_error"] or "",
        )


class SchedulerEngine:
    """Unified asyncio scheduler for periodic maintenance tasks."""

    def __init__(self, state):
        self.state = state
        self._task: asyncio.Task | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}  # task_type → running task
        self._paused: bool = False
        self._lock = asyncio.Lock()
        self._schedules: dict[str, ScheduleEntry] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self):
        """Load schedules from DB, seed defaults if empty, start main loop."""
        await self.prepare()
        await self.start_loop()
        logger.info(f"Scheduler started with {len(self._schedules)} schedules")

    async def prepare(self):
        """Load schedules from DB and seed defaults if empty.

        Does NOT start the run loop, so it is safe to call early (e.g. before
        the startup hunt cycle) — schedules become visible in the UI without
        any task being triggered yet.
        """
        await self._load_schedules()
        await self._seed_defaults_if_empty()

    async def start_loop(self):
        """Start the main tick loop. Idempotent."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the main loop and all running task instances."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        for t in list(self._running_tasks.values()):
            t.cancel()
        await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        self._running_tasks.clear()

    # ── DB persistence ─────────────────────────────────────────────────

    async def _load_schedules(self):
        """Load all schedules from the DB into in-memory cache."""
        try:
            conn = self.state._db()
            rows = conn.execute("SELECT * FROM schedules").fetchall()
            conn.close()
            self._schedules = {row["id"]: ScheduleEntry.from_row(row) for row in rows}
        except Exception as e:
            logger.warning(f"Scheduler load failed: {e}")
            self._schedules = {}

    def _persist(self, entry: ScheduleEntry):
        """Upsert a single schedule entry into the DB."""
        try:
            conn = self.state._db()
            conn.execute(
                "INSERT OR REPLACE INTO schedules "
                "(id, name, task_type, enabled, interval_sec, config, "
                "last_run, next_run, last_status, last_duration_s, last_error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry.id,
                    entry.name,
                    entry.task_type,
                    1 if entry.enabled else 0,
                    entry.interval_sec,
                    json.dumps(entry.config),
                    entry.last_run,
                    entry.next_run,
                    entry.last_status,
                    entry.last_duration_s,
                    entry.last_error,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Scheduler persist failed: {e}")

    def _db_delete(self, sid: str):
        try:
            conn = self.state._db()
            conn.execute("DELETE FROM schedules WHERE id=?", (sid,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Scheduler delete failed: {e}")

    async def _seed_defaults_if_empty(self):
        """Seed default schedules when the DB table is empty (first run)."""
        if self._schedules:
            return
        for d in DEFAULT_SCHEDULES:
            entry = ScheduleEntry(
                id=d["id"],
                name=d["name"],
                task_type=d["task_type"],
                enabled=bool(d["enabled"]),
                interval_sec=d["interval_sec"],
                config=d["config"] if isinstance(d["config"], dict) else json.loads(d["config"]),
            )
            self._schedules[entry.id] = entry
            self._persist(entry)
        logger.info(f"Seeded {len(DEFAULT_SCHEDULES)} default schedules")

    async def restore_defaults(self) -> list[str]:
        """Re-add any missing default schedules without overwriting existing ones.

        Returns the list of newly added schedule ids.
        """
        if not self._schedules:
            await self._load_schedules()
        added = []
        async with self._lock:
            for d in DEFAULT_SCHEDULES:
                if d["id"] in self._schedules:
                    continue
                entry = ScheduleEntry(
                    id=d["id"],
                    name=d["name"],
                    task_type=d["task_type"],
                    enabled=bool(d["enabled"]),
                    interval_sec=d["interval_sec"],
                    config=d["config"] if isinstance(d["config"], dict) else json.loads(d["config"]),
                )
                if entry.enabled and entry.interval_sec > 0:
                    entry.next_run = time.time() + entry.interval_sec
                self._schedules[entry.id] = entry
                self._persist(entry)
                added.append(entry.id)
        if added:
            logger.info(f"Restored {len(added)} missing default schedules: {added}")
        return added

    # ── Main loop ──────────────────────────────────────────────────────

    async def _run_loop(self):
        """Check every _TICK_INTERVAL seconds for due schedules and trigger them."""
        while True:
            try:
                await asyncio.sleep(_TICK_INTERVAL)
                if self._paused:
                    continue
                now = time.time()
                for sid, entry in list(self._schedules.items()):
                    if not entry.enabled or entry.interval_sec <= 0:
                        continue
                    if entry.next_run == 0:
                        entry.next_run = now + entry.interval_sec
                        self._persist(entry)
                    if now >= entry.next_run:
                        await self._trigger(sid)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(10)

    # ── Task triggering ────────────────────────────────────────────────

    async def _trigger(self, sid: str):
        """Trigger a schedule if mutex/environment checks pass."""
        entry = self._schedules.get(sid)
        if entry is None:
            return
        task_def = TASK_TYPES.get(entry.task_type)
        if task_def is None:
            return

        def _skip(reason):
            entry.last_status = "skipped"
            entry.next_run = time.time() + entry.interval_sec
            self._persist(entry)
            self.state._emit(f"Scheduler: skipped '{entry.name}' — {reason}", "warn")

        # Check if this task_type is already running
        if entry.task_type in self._running_tasks:
            _skip("already running")
            return

        # Check if an external fetch is already in progress (e.g. the
        # startup hunt cycle is downloading the same lists). Skip gracefully
        # instead of letting the executor raise RuntimeError.
        busy_flag = task_def.get("busy_flag")
        if busy_flag and getattr(self.state, busy_flag, False):
            _skip("fetch in progress")
            return

        # Check mutex conflicts
        for conflict_type in task_def["mutex_with"]:
            if conflict_type in self._running_tasks:
                _skip(f"waiting on {conflict_type}")
                return

        # Environment checks
        if task_def["respect_pause"] and self.state._paused:
            _skip("hunt paused")
            return

        if task_def["respect_internet"]:
            try:
                internet_ok = await self.state.is_internet_alive()
            except Exception:
                internet_ok = False
            if not internet_ok:
                _skip("internet down")
                return

        # Launch the task
        entry.last_status = "running"
        entry.last_run = time.time()
        self._persist(entry)
        self.state._emit(f"Scheduler: starting '{entry.name}'", "info")

        task = asyncio.create_task(self._run_with_tracking(sid))
        self._running_tasks[entry.task_type] = task

    async def _run_with_tracking(self, sid: str):
        """Execute a scheduled task, update status/duration/error on completion."""
        entry = self._schedules.get(sid)
        if entry is None:
            return
        t0 = time.time()
        try:
            await self._execute_task(entry)
            entry.last_status = "ok"
            entry.last_error = ""
            self.state._emit(
                f"Scheduler: '{entry.name}' done in {entry.last_duration_s}s", "ok",
            )
        except asyncio.CancelledError:
            entry.last_status = "failed"
            entry.last_error = "cancelled"
            self.state._emit(f"Scheduler: '{entry.name}' cancelled", "warn")
            raise
        except Exception as e:
            entry.last_status = "failed"
            entry.last_error = str(e)[:500]
            logger.error(f"Schedule '{sid}' failed: {e}")
            self.state._emit(f"Scheduler: '{entry.name}' failed: {e}", "error")
        finally:
            entry.last_duration_s = round(time.time() - t0, 2)
            entry.next_run = time.time() + entry.interval_sec
            self._running_tasks.pop(entry.task_type, None)
            self._persist(entry)

    # ── Task executors ─────────────────────────────────────────────────

    async def _execute_task(self, entry: ScheduleEntry):
        """Dispatch to the appropriate executor based on task_type."""
        tt = entry.task_type
        if tt == "hunt_cycle":
            await self._execute_hunt_cycle(entry)
        elif tt == "ip_blacklist":
            await self._execute_ip_blacklist(entry)
        elif tt == "blocklist":
            await self._execute_blocklist(entry)
        elif tt == "health_check":
            await self._execute_health_check(entry)
        elif tt == "history":
            await self._execute_history(entry)
        elif tt == "clear_dead":
            await self._execute_clear_dead(entry)
        elif tt == "backup":
            await self._execute_backup(entry)
        else:
            raise ValueError(f"Unknown task type: {tt}")

    async def _execute_hunt_cycle(self, entry: ScheduleEntry):
        """Start a full hunt cycle and wait for it to complete."""
        if self.state._hunt_running:
            raise RuntimeError("Hunt already running")
        ok = self.state.start_hunt()
        if not ok:
            raise RuntimeError("start_hunt() returned False")
        # Wait for the hunt cycle task to finish (download → blacklist → validate).
        deadline = time.time() + 3600  # 1h max
        while self.state.task is not None and not self.state.task.done():
            if time.time() > deadline:
                raise TimeoutError("Hunt cycle exceeded 1 hour")
            await asyncio.sleep(2)

    async def _execute_ip_blacklist(self, entry: ScheduleEntry):
        """Download IP blacklist sources."""
        if getattr(self.state, "_fetching_ip_blacklists", False):
            raise RuntimeError("IP blacklist fetch already in progress")
        self.state._emit("Scheduler: refreshing IP blacklists...", "info")
        results = await self.state._download_ip_blacklists()
        total = sum(results.values())
        self.state._emit(f"Scheduler: refreshed {total} IP blacklist entries", "info")

    async def _execute_blocklist(self, entry: ScheduleEntry):
        """Download country blocklists."""
        if getattr(self.state, "_fetching_blocklists", False):
            raise RuntimeError("Blocklist fetch already in progress")
        self.state._emit("Scheduler: refreshing country blocklists...", "info")
        results = await self.state._download_blocklists()
        total = sum(results.values())
        self.state._emit(f"Scheduler: refreshed {total} blocklist entries", "info")

    async def _execute_health_check(self, entry: ScheduleEntry):
        """Re-validate alive proxies."""
        if self.state._health_running:
            raise RuntimeError("Health check already running")
        await self.state._health_check(manual=False)

    async def _execute_history(self, entry: ScheduleEntry):
        """Record history snapshot and run retention cleanup."""
        self.state._push_history()
        try:
            conn = self.state._stats_db()
            now = time.time()
            conn.execute("DELETE FROM traffic_log WHERE ts < ?", (now - 7 * 86400,))
            conn.execute("DELETE FROM events WHERE ts < ?", (now - 30 * 86400,))
            conn.execute("DELETE FROM actions WHERE ts < ?", (now - 30 * 86400,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Scheduler history cleanup: {e}")

    async def _execute_clear_dead(self, entry: ScheduleEntry):
        """Remove dead proxies from the pool."""
        dead_addrs = [
            a for a, r in self.state.ratings.items()
            if r.last_status == "failed" and not r.is_favorite and not r.in_grace
        ]
        for a in dead_addrs:
            del self.state.ratings[a]
        self.state._emit(f"Scheduler: cleared {len(dead_addrs)} dead proxies", "warn")
        self.state._save_state()
        self.state._save_working_file()
        self.state._log_action("scheduler.clear_dead", f"{len(dead_addrs)} proxies")

    async def _execute_backup(self, entry: ScheduleEntry):
        """Create a database backup to the data directory."""
        import os
        from hunt.constants import DATA_DIR
        groups = entry.config.get("groups", "all")
        if groups == "all":
            groups = list(self.state.get_backup_groups())
            groups = [g["key"] for g in groups]
        elif isinstance(groups, str):
            groups = [groups]
        data = self.state.create_backup(groups)
        backup_dir = DATA_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        filename = f"backup_{int(time.time())}.json"
        with open(backup_dir / filename, "wb") as f:
            f.write(data)
        self.state._emit(f"Scheduler: backup saved as {filename}", "ok")
        self.state._log_action("scheduler.backup", filename)

    # ── Manual trigger ─────────────────────────────────────────────────

    async def trigger_now(self, sid: str) -> bool:
        """Trigger a schedule immediately, outside its normal cadence."""
        entry = self._schedules.get(sid)
        if entry is None:
            return False
        await self._trigger(sid)
        return True

    # ── CRUD ───────────────────────────────────────────────────────────

    def list_schedules(self) -> list[dict]:
        """Return all schedules as dicts, sorted by id."""
        return [e.to_dict() for _, e in sorted(self._schedules.items())]

    def get_schedule(self, sid: str) -> dict | None:
        entry = self._schedules.get(sid)
        return entry.to_dict() if entry else None

    async def add_schedule(self, sid: str, name: str, task_type: str,
                           interval_sec: int, config: dict | None = None,
                           enabled: bool = True) -> dict:
        """Create a new schedule."""
        if task_type not in TASK_TYPES:
            raise ValueError(f"Unknown task type: {task_type}")
        if sid in self._schedules:
            raise ValueError(f"Schedule '{sid}' already exists")
        entry = ScheduleEntry(
            id=sid,
            name=name,
            task_type=task_type,
            enabled=enabled,
            interval_sec=interval_sec,
            config=config or {},
        )
        if enabled and interval_sec > 0:
            entry.next_run = time.time() + interval_sec
        async with self._lock:
            self._schedules[sid] = entry
            self._persist(entry)
        return entry.to_dict()

    async def update_schedule(self, sid: str, **fields) -> dict | None:
        """Update fields of an existing schedule."""
        async with self._lock:
            entry = self._schedules.get(sid)
            if entry is None:
                return None
            if "name" in fields:
                entry.name = fields["name"]
            if "task_type" in fields:
                if fields["task_type"] not in TASK_TYPES:
                    raise ValueError(f"Unknown task type: {fields['task_type']}")
                entry.task_type = fields["task_type"]
            if "interval_sec" in fields:
                entry.interval_sec = fields["interval_sec"]
                # Recalculate next_run based on last_run + new interval
                if entry.enabled and entry.interval_sec > 0:
                    base = entry.last_run if entry.last_run > 0 else time.time()
                    entry.next_run = base + entry.interval_sec
            if "config" in fields:
                entry.config = fields["config"]
            if "enabled" in fields:
                entry.enabled = fields["enabled"]
                if entry.enabled and entry.interval_sec > 0:
                    entry.next_run = time.time() + entry.interval_sec
                elif not entry.enabled:
                    entry.next_run = 0
            self._persist(entry)
            return entry.to_dict()

    async def delete_schedule(self, sid: str) -> bool:
        """Delete a schedule."""
        async with self._lock:
            if sid not in self._schedules:
                return False
            self._schedules.pop(sid, None)
            self._db_delete(sid)
            return True

    async def toggle_schedule(self, sid: str) -> dict | None:
        """Toggle the enabled state of a schedule."""
        async with self._lock:
            entry = self._schedules.get(sid)
            if entry is None:
                return None
            entry.enabled = not entry.enabled
            if entry.enabled and entry.interval_sec > 0:
                entry.next_run = time.time() + entry.interval_sec
            else:
                entry.next_run = 0
            self._persist(entry)
            return entry.to_dict()

    # ── Global pause/resume ────────────────────────────────────────────

    def pause_all(self):
        self._paused = True
        self.state._emit("Scheduler paused", "warn")

    def resume_all(self):
        self._paused = False
        self.state._emit("Scheduler resumed", "ok")

    def is_paused(self) -> bool:
        return self._paused

    def get_running_task_types(self) -> list[str]:
        return list(self._running_tasks.keys())

    def get_status(self) -> dict:
        return {
            "running": self._task is not None and not self._task.done(),
            "paused": self._paused,
            "running_tasks": list(self._running_tasks.keys()),
            "schedule_count": len(self._schedules),
        }

    def get_log(self, limit: int = 50) -> list[dict]:
        """Return recent scheduler-related events and actions, merged and sorted by time desc."""
        results = []
        try:
            conn = self.state._stats_db()
            # Events whose message contains 'Scheduler' or 'Schedule'
            rows = conn.execute(
                "SELECT ts, seq, type, msg FROM events "
                "WHERE msg LIKE '%Scheduler%' OR msg LIKE '%schedule%' "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            for r in rows:
                results.append({
                    "ts": r["ts"], "seq": r["seq"],
                    "type": r["type"], "msg": r["msg"],
                    "source": "event",
                })
            # Actions whose action contains 'schedule'
            rows = conn.execute(
                "SELECT ts, action, detail FROM actions "
                "WHERE action LIKE '%schedule%' OR action LIKE '%scheduler%' "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            for r in rows:
                results.append({
                    "ts": r["ts"], "seq": 0,
                    "type": "action",
                    "msg": f"{r['action']}: {r['detail']}",
                    "source": "action",
                })
            conn.close()
        except Exception as e:
            logger.warning(f"Scheduler log query: {e}")
        results.sort(key=lambda x: x["ts"], reverse=True)
        return results[:limit]
