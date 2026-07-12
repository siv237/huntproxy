"""Task executor — runs scheduled tasks, decoupled from the scheduler's
planning logic (queue, mutex, busy-flag, due-check).

The scheduler decides *when* to run a task; the executor decides *how*.
This separation follows Single Responsibility: planning and execution are
independent concerns that can evolve without coupled changes.

Executors are registered as a ``{task_type: coroutine}`` registry, making
the dispatch Open/Closed: adding a new task type means registering a new
executor, not editing an if/elif chain.
"""

import time

from hunt.constants import DATA_DIR, logger
from hunt.scheduler import ScheduleEntry


class TaskExecutor:
    """Registry of task executors, keyed by task_type.

    Each executor is an ``async def(state, entry) -> None`` that performs
    the actual work.  The executor raises on failure; the scheduler's
    ``_run_with_tracking`` wrapper catches and records the error.
    """

    def __init__(self, state):
        self.state = state
        self._executors: dict[str, callable] = {}
        self._register_defaults()

    def register(self, task_type: str, handler):
        """Register or override an executor for a task type."""
        self._executors[task_type] = handler

    def get(self, task_type: str):
        """Return the executor for a task type, or None."""
        return self._executors.get(task_type)

    async def run(self, entry: ScheduleEntry):
        """Dispatch ``entry`` to its registered executor.

        Raises ``ValueError`` for unknown task types (which the scheduler
        records as a failed run).
        """
        handler = self._executors.get(entry.task_type)
        if handler is None:
            raise ValueError(f"Unknown task type: {entry.task_type}")
        await handler(self.state, entry)

    # ── Default executors ───────────────────────────────────────────────

    def _register_defaults(self):
        self.register("proxy_check", _execute_proxy_check)
        self.register("ip_blacklist", _execute_ip_blacklist)
        self.register("blocklist", _execute_blocklist)
        self.register("health_check", _execute_health_check)
        self.register("history", _execute_history)
        self.register("clear_dead", _execute_clear_dead)
        self.register("backup", _execute_backup)


# ── Executor implementations ───────────────────────────────────────────
# Each is a module-level async function ``(state, entry) -> None`` so it
# can be registered independently and tested in isolation.


async def _execute_proxy_check(state, entry: ScheduleEntry):
    """Re-validate ALL existing proxies in the pool without collecting new ones.

    This is the scheduled equivalent of a manual "check" — it re-validates
    every proxy currently in ratings.  Unlike a full hunt, it never
    downloads proxy source lists or blocklists (those are refreshed by
    their own separate schedules).
    """
    candidates = [r for r in state.ratings.values() if not r.in_blacklist]
    if not candidates:
        state._emit("Scheduler: proxy_check — no proxies to validate", "info")
        return

    candidates.sort(key=lambda r: r.first_seen, reverse=True)
    addrs = [r.address for r in candidates]
    state._emit(f"Scheduler: proxy_check — re-validating {len(addrs)} proxies", "info")
    state.checking_total = len(addrs)
    state.checked = 0
    state.working = 0
    state.failed = 0
    await state._validate_all(addrs)
    state._flush_proxy_checks()
    state._emit(
        f"Scheduler: proxy_check — done "
        f"({state.working} ok, {state.failed} failed)",
        "ok",
    )


async def _execute_ip_blacklist(state, entry: ScheduleEntry):
    """Download IP blacklist sources."""
    if getattr(state, "_fetching_ip_blacklists", False):
        raise RuntimeError("IP blacklist fetch already in progress")
    state._emit("Scheduler: refreshing IP blacklists...", "info")
    results = await state._download_ip_blacklists()
    total = sum(results.values())
    state._emit(f"Scheduler: refreshed {total} IP blacklist entries", "info")


async def _execute_blocklist(state, entry: ScheduleEntry):
    """Download country blocklists."""
    if getattr(state, "_fetching_blocklists", False):
        raise RuntimeError("Blocklist fetch already in progress")
    state._emit("Scheduler: refreshing country blocklists...", "info")
    results = await state._download_blocklists()
    total = sum(results.values())
    state._emit(f"Scheduler: refreshed {total} blocklist entries", "info")


async def _execute_health_check(state, entry: ScheduleEntry):
    """Re-validate alive proxies."""
    if state._health_running:
        raise RuntimeError("Health check already running")
    await state._health_check(manual=False)


async def _execute_history(state, entry: ScheduleEntry):
    """Record history snapshot and run retention cleanup."""
    state._push_history()
    try:
        conn = state._stats_db()
        now = time.time()
        conn.execute("DELETE FROM traffic_log WHERE ts < ?", (now - 7 * 86400,))
        conn.execute("DELETE FROM events WHERE ts < ?", (now - 30 * 86400,))
        conn.execute("DELETE FROM actions WHERE ts < ?", (now - 30 * 86400,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Scheduler history cleanup: {e}")


async def _execute_clear_dead(state, entry: ScheduleEntry):
    """Remove dead proxies from the pool."""
    dead_addrs = [
        a for a, r in state.ratings.items()
        if r.last_status == "failed" and not r.is_favorite and not r.in_grace
    ]
    for a in dead_addrs:
        del state.ratings[a]
    state._emit(f"Scheduler: cleared {len(dead_addrs)} dead proxies", "warn")
    state._save_state()
    state._save_working_file()
    state._log_action("scheduler.clear_dead", f"{len(dead_addrs)} proxies")


async def _execute_backup(state, entry: ScheduleEntry):
    """Create a database backup to the data directory."""
    groups = entry.config.get("groups", "all")
    if groups == "all":
        groups = list(state.get_backup_groups())
        groups = [g["key"] for g in groups]
    elif isinstance(groups, str):
        groups = [groups]
    data = state.create_backup(groups)
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = f"backup_{int(time.time())}.json"
    with open(backup_dir / filename, "wb") as f:
        f.write(data)
    state._emit(f"Scheduler: backup saved as {filename}", "ok")
    state._log_action("scheduler.backup", filename)
