"""Unified asyncio scheduler for periodic maintenance tasks.

Replaces the ad-hoc _history_loop, _ip_blacklist_loop,
_blocklist_loop and _health_loop sleep-cycles with a single
configurable, DB-persisted, runtime-editable scheduler.
"""

import asyncio
import json
import time
from typing import Any

from hunt.constants import logger
from hunt.schedule_entry import ScheduleEntry, TASK_TYPES, DEFAULT_SCHEDULES
from hunt.scheduler_persistence import SchedulerPersistenceMixin
from hunt.scheduler_api import SchedulerApiMixin


_TICK_INTERVAL = 5  # seconds


class SchedulerEngine(SchedulerPersistenceMixin, SchedulerApiMixin):

    def __init__(self, state):
        self.state = state
        self._task: asyncio.Task | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}  # task_type → running task
        self._queue: dict[str, float] = {}  # sid → queued_at timestamp
        self._paused: bool = False
        self._stopped: bool = False
        self._lock = asyncio.Lock()
        self._schedules: dict[str, ScheduleEntry] = {}
        # Task executor — decoupled from planning logic.  Tests can stub
        # individual executors via self.executor.register(tt, fn).
        from hunt.task_executor import TaskExecutor
        self.executor = TaskExecutor(state)

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

    def _is_busy_flag_stale(self, busy_flag: str) -> bool:
        """Return True if a busy-flag is True but no live task backs it.

        For _hunt_running the live task can be either the startup cycle
        (self.state._startup_task) or the hunt cycle (self.state.task),
        since both set the flag.  If neither is alive, the flag is leftover
        from a crashed/destroyed/GC'd run and should be cleared.
        """
        if not getattr(self.state, busy_flag, False):
            return False
        if busy_flag == "_hunt_running":
            for attr in ("_startup_task", "task"):
                t = getattr(self.state, attr, None)
                if t is not None and not t.done():
                    return False
            return True
        return True

    def _check_busy_flag(self, task_def: dict) -> bool:
        """Clear a stale busy-flag and return True if the task may proceed.

        Returns False when a genuinely active busy-flag blocks the task.
        """
        busy_flag = task_def.get("busy_flag")
        if not busy_flag:
            return True
        if not getattr(self.state, busy_flag, False):
            return True
        if self._is_busy_flag_stale(busy_flag):
            self.state._emit(
                f"Scheduler: clearing stale busy-flag '{busy_flag}'",
                "warn",
            )
            setattr(self.state, busy_flag, False)
            self.state._save_state()
            return True
        return False

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
        # startup hunt cycle is downloading the same lists).  A stale flag
        # (left True by a crashed/destroyed previous run) is cleared so the
        # task is not blocked forever.
        if not self._check_busy_flag(task_def):
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
        """Dispatch to the TaskExecutor registry based on task_type.

        Planning and execution are decoupled: the scheduler decides *when*
        to run a task, the TaskExecutor decides *how*.  Executors live in
        ``hunt.task_executor`` and are registered in a dict, so adding a
        new task type does not require editing this if/elif chain.
        """
        await self.executor.run(entry)

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
        # task behind it, the flag is leftover from a crash/restart/GC.
        # Uses the same logic as the automatic _try_launch path.
        busy_flag = task_def.get("busy_flag")
        if busy_flag and getattr(self.state, busy_flag, False):
            if self._is_busy_flag_stale(busy_flag):
                self.state._emit(
                    f"Scheduler: clearing stale busy-flag '{busy_flag}' for manual run of '{entry.name}'",
                    "warn",
                )
                setattr(self.state, busy_flag, False)
                self.state._save_state()
            else:
                self.state._emit(
                    f"Scheduler: '{entry.name}' queued — busy-flag '{busy_flag}' is active (hunt running)",
                    "warn",
                )
                self._enqueue(sid)
                return True

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

