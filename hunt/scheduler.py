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


class SchedulerEngine:
    """Unified asyncio scheduler for periodic maintenance tasks."""

    def __init__(self, state):
        self.state = state
        self._task: asyncio.Task | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}  # task_type → running task
        self._queue: dict[str, float] = {}  # sid → queued_at timestamp
        self._paused: bool = False
        self._stopped: bool = False
        self._lock = asyncio.Lock()
        self._schedules: dict[str, ScheduleEntry] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self):
        """Load schedules from DB, seed defaults if empty, start main loop."""
        await self.prepare()
        await self.start_loop()

    async def prepare(self):
        """Load schedules from DB and seed defaults if empty.

        Does NOT start the run loop, so it is safe to call early (e.g. before
        the startup hunt cycle) — schedules become visible in the UI without
        any task being triggered yet.
        """
        await self._load_schedules()
        await self._seed_defaults_if_empty()
        # Re-add any missing default schedules (e.g. proxy_check was added after
        # the DB was first seeded with the old hunt_cycle schedule).
        await self.restore_defaults()

    async def start_loop(self):
        """Start the main tick loop. Idempotent."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        """Stop the main loop and all running task instances."""
        self._stopped = True
        self._queue.clear()  # prevent new launches during shutdown
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
        self._queue.clear()

    # ── DB persistence ─────────────────────────────────────────────────

    async def _load_schedules(self):
        """Load all schedules from the DB into in-memory cache.

        Schedules whose task_type is no longer known (e.g. 'hunt_cycle' was
        removed) are purged from the DB so stale rows don't surface as 404s
        in the UI.
        """
        try:
            conn = self.state._db()
            rows = conn.execute("SELECT * FROM schedules").fetchall()
            self._schedules = {}
            for row in rows:
                if row["task_type"] not in TASK_TYPES:
                    logger.info(f"Scheduler: dropping stale schedule '{row['id']}' (unknown task_type '{row['task_type']}')")
                    conn.execute("DELETE FROM schedules WHERE id=?", (row["id"],))
                    continue
                self._schedules[row["id"]] = ScheduleEntry.from_row(row)
            conn.commit()
            conn.close()
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
                "last_run, last_ok, next_run, last_status, last_duration_s, last_error) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry.id,
                    entry.name,
                    entry.task_type,
                    1 if entry.enabled else 0,
                    entry.interval_sec,
                    json.dumps(entry.config),
                    entry.last_run,
                    entry.last_ok,
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
        """Check every _TICK_INTERVAL seconds for due schedules and queue them.

        A schedule is "due" when at least interval_sec has passed since its
        last SUCCESSFUL completion (last_ok). When due, the schedule is placed
        in the pending queue rather than skipped — it will run as soon as its
        mutex/busy constraints are satisfiable.
        """
        while True:
            try:
                await asyncio.sleep(_TICK_INTERVAL)
                if self._paused:
                    continue
                now = time.time()
                for sid, entry in list(self._schedules.items()):
                    if not entry.enabled or entry.interval_sec <= 0:
                        continue
                    if entry.task_type in self._running_tasks:
                        continue
                    if sid in self._queue:
                        continue
                    if entry.is_due(now):
                        self._enqueue(sid)
                await self._drain_queue()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(10)

    # ── Queue ──────────────────────────────────────────────────────────

    def _enqueue(self, sid: str):
        """Mark a schedule as pending — it will be launched when possible."""
        entry = self._schedules.get(sid)
        if entry is None or sid in self._queue:
            return
        self._queue[sid] = time.time()
        entry.last_status = "queued"
        entry.next_run = time.time() + entry.interval_sec
        self._persist(entry)

    async def _drain_queue(self):
        """Try to launch every queued schedule whose constraints are now met.

        Unlike the old skip logic, a queued task is never silently dropped —
        it stays in the queue until it can actually run.
        """
        if not self._queue:
            return
        if self._stopped:
            # Shutting down — don't launch new tasks.
            return
        for sid in list(self._queue.keys()):
            entry = self._schedules.get(sid)
            if entry is None:
                self._queue.pop(sid, None)
                continue
            if entry.task_type in self._running_tasks:
                continue
            launched = await self._try_launch(sid)
            if launched:
                self._queue.pop(sid, None)

    # ── Task triggering ────────────────────────────────────────────────

    async def _try_launch(self, sid: str) -> bool:
        """Try to launch a schedule. Returns True if launched, False if blocked.

        Unlike the old _trigger, a blocked task is NOT skipped — it remains
        queued so it will be retried on the next tick.
        """
        entry = self._schedules.get(sid)
        if entry is None:
            return False
        task_def = TASK_TYPES.get(entry.task_type)
        if task_def is None:
            return False

        # Check if this task_type is already running
        if entry.task_type in self._running_tasks:
            return False

        # Check if an external fetch is already in progress (e.g. the
        # startup hunt cycle is downloading the same lists).
        busy_flag = task_def.get("busy_flag")
        if busy_flag and getattr(self.state, busy_flag, False):
            return False

        # Check mutex conflicts
        for conflict_type in task_def["mutex_with"]:
            if conflict_type in self._running_tasks:
                return False

        # Environment checks
        if task_def["respect_pause"] and self.state._paused:
            return False

        if task_def["respect_internet"]:
            try:
                internet_ok = await self.state.is_internet_alive()
            except Exception:
                internet_ok = False
            if not internet_ok:
                return False

        # Launch the task
        entry.last_status = "running"
        entry.last_run = time.time()
        self._persist(entry)
        self.state._emit(f"Scheduler: starting '{entry.name}'", "info")

        task = asyncio.create_task(self._run_with_tracking(sid))
        self._running_tasks[entry.task_type] = task
        return True

    async def _trigger(self, sid: str):
        """Manual trigger: queue a schedule (runs as soon as possible)."""
        entry = self._schedules.get(sid)
        if entry is None:
            return
        self._enqueue(sid)
        await self._drain_queue()

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
            entry.last_ok = time.time()
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
            # Schedule the next run from COMPLETION time. The real trigger
            # condition is last_ok + interval_sec (see is_due), so next_run is
            # only a cosmetic hint for the UI.
            entry.next_run = time.time() + entry.interval_sec
            self._running_tasks.pop(entry.task_type, None)
            self._persist(entry)
            # After a task finishes, try to drain the queue — a queued task
            # that was blocked by this one may now be runnable. Swallow errors
            # so a pending CancelledError is not masked during shutdown.
            try:
                await self._drain_queue()
            except Exception:
                pass

    # ── Task executors ─────────────────────────────────────────────────

    async def _execute_task(self, entry: ScheduleEntry):
        """Dispatch to the appropriate executor based on task_type."""
        tt = entry.task_type
        if tt == "proxy_check":
            await self._execute_proxy_check(entry)
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

    async def _execute_proxy_check(self, entry: ScheduleEntry):
        """Re-validate ALL existing proxies in the pool without collecting new ones.

        This is the scheduled equivalent of a manual "check" — it re-validates
        every proxy currently in ratings.  Unlike a full hunt, it never
        downloads proxy source lists or blocklists (those are refreshed by
        their own separate schedules).
        """
        state = self.state

        # Re-validate every non-blacklisted proxy in the pool.
        candidates = [r for r in state.ratings.values() if not r.in_blacklist]
        if not candidates:
            state._emit("Scheduler: proxy_check — no proxies to validate", "info")
            return

        # Sort by first_seen descending — check newest proxies first so
        # fresh candidates are validated before stale dead entries.
        candidates.sort(key=lambda r: r.first_seen, reverse=True)
        addrs = [r.address for r in candidates]
        state._emit(f"Scheduler: proxy_check — re-validating {len(addrs)} proxies", "info")
        state.checking_total = len(addrs)
        state.checked = 0
        state.working = 0
        state.failed = 0
        await state._validate_all(addrs)
        state._save_state()
        state._save_working_file()
        state._emit(
            f"Scheduler: proxy_check — done "
            f"({state.working} ok, {state.failed} failed)",
            "ok",
        )

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
        """Trigger a schedule immediately, bypassing the queue and busy-flag guards.

        Manual "Run Now" must launch right away — it is not subject to the
        normal due/queue logic.  Stale busy-flags (e.g. a _hunt_running left
        True by a crashed previous run) are cleared so the task can start.
        Mutex conflicts are still honoured to avoid running incompatible
        tasks at the same time.
        """
        entry = self._schedules.get(sid)
        if entry is None:
            return False
        task_def = TASK_TYPES.get(entry.task_type)
        if task_def is None:
            return False

        # Already running this task type — nothing to do.
        if entry.task_type in self._running_tasks:
            return False

        # Clear a stale busy-flag: if the flag is True but there is no live
        # asyncio task of this type, the flag is leftover from a crash/restart.
        busy_flag = task_def.get("busy_flag")
        if busy_flag and getattr(self.state, busy_flag, False):
            self.state._emit(
                f"Scheduler: clearing stale busy-flag '{busy_flag}' for manual run of '{entry.name}'",
                "warn",
            )
            setattr(self.state, busy_flag, False)
            self.state._save_state()

        # Remove from queue if present — we're launching directly.
        self._queue.pop(sid, None)

        # Honour mutex conflicts: if a conflicting task is running, queue this
        # one so it launches automatically when the blocker finishes.  This is
        # better than rejecting the manual run with a 404.
        for conflict_type in task_def["mutex_with"]:
            if conflict_type in self._running_tasks:
                self._enqueue(sid)
                self.state._emit(
                    f"Scheduler: '{entry.name}' queued — waiting for '{conflict_type}' to finish",
                    "warn",
                )
                return True

        # Launch directly, skipping the queue.
        entry.last_status = "running"
        entry.last_run = time.time()
        self._persist(entry)
        self.state._emit(f"Scheduler: manual run '{entry.name}'", "info")
        task = asyncio.create_task(self._run_with_tracking(sid))
        self._running_tasks[entry.task_type] = task
        return True

    async def cancel_running(self, sid: str) -> bool:
        """Cancel a running (or queued) schedule instance.

        Returns True if something was cancelled/dequeued, False otherwise.
        """
        entry = self._schedules.get(sid)
        if entry is None:
            return False
        # Remove from queue if present.
        if sid in self._queue:
            self._queue.pop(sid, None)
            entry.last_status = "ok" if entry.last_ok > 0 else "never"
            self._persist(entry)
            self.state._emit(f"Scheduler: removed '{entry.name}' from queue", "info")
            return True
        # Cancel the running task.
        task = self._running_tasks.get(entry.task_type)
        if task is not None and not task.done():
            task.cancel()
            self.state._emit(f"Scheduler: cancelling '{entry.name}'", "warn")
            return True
        return False

    def list_schedules(self) -> list[dict]:
        """Return all schedules as dicts, sorted by id, with live countdown."""
        now = time.time()
        out = []
        for sid, e in sorted(self._schedules.items()):
            d = e.to_dict()
            d["queued"] = sid in self._queue
            # Realtime countdown to the next run.
            if not e.enabled or e.interval_sec <= 0:
                d["countdown"] = None
            elif e.task_type in self._running_tasks:
                d["countdown"] = -1  # currently running
            elif sid in self._queue:
                d["countdown"] = 0  # queued, waiting to start
            else:
                if e.last_ok > 0:
                    due_at = e.last_ok + e.interval_sec
                else:
                    # Never succeeded yet — use next_run hint as the countdown basis
                    due_at = e.next_run if e.next_run > 0 else 0
                remaining = due_at - now
                d["countdown"] = max(0, int(remaining))
            out.append(d)
        return out

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
                # next_run is a cosmetic hint; the real trigger is last_ok+interval
                if entry.enabled and entry.interval_sec > 0:
                    base = entry.last_ok if entry.last_ok > 0 else time.time()
                    entry.next_run = base + entry.interval_sec
            if "config" in fields:
                entry.config = fields["config"]
            if "enabled" in fields:
                entry.enabled = fields["enabled"]
                if entry.enabled and entry.interval_sec > 0:
                    base = entry.last_ok if entry.last_ok > 0 else time.time()
                    entry.next_run = base + entry.interval_sec
                elif not entry.enabled:
                    entry.next_run = 0
                    self._queue.pop(entry.id, None)
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
                base = entry.last_ok if entry.last_ok > 0 else time.time()
                entry.next_run = base + entry.interval_sec
            else:
                entry.next_run = 0
                self._queue.pop(entry.id, None)
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
            "queued": list(self._queue.keys()),
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
