"""Task executor — runs scheduled tasks, decoupled from the scheduler's
planning logic (queue, mutex, busy-flag, due-check).

The scheduler decides *when* to run a task; the executor decides *how*.
This separation follows Single Responsibility: planning and execution are
independent concerns that can evolve without coupled changes.

Executors are registered as a ``{task_type: coroutine}`` registry, making
the dispatch Open/Closed: adding a new task type means registering a new
executor, not editing an if/elif chain.
"""

import asyncio
import sqlite3
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
        self.register("source_refresh", _execute_source_refresh)
        self.register("ip_blacklist", _execute_ip_blacklist)
        self.register("blocklist", _execute_blocklist)
        self.register("health_check", _execute_health_check)
        self.register("history", _execute_history)
        self.register("clear_dead", _execute_clear_dead)
        self.register("backup", _execute_backup)
        self.register("db_maintenance", _execute_db_maintenance)


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


async def _execute_source_refresh(state, entry: ScheduleEntry):
    """Download proxy source lists and queue fresh addresses for validation.

    Collect-only: new addresses are added to ratings as untested (score 0,
    not eligible for the pool).  The regular proxy_check schedule validates
    them — newest first — on its next run, so this task never touches the
    shared validation counters and needs no mutex with proxy_check /
    health_check.
    """
    state._emit("Scheduler: refreshing proxy sources...", "info")
    raw = await state._download_sources()
    new = [a for a in raw if a not in state.ratings]
    for a in new:
        state.ratings[a] = state._create_rating(a, "", "")
        state._dirty_ratings.add(a)
    if new:
        state._save_dirty_ratings()
    state._emit(
        f"Scheduler: {len(new)} fresh proxies queued for validation "
        f"({len(raw)} total in sources)",
        "ok",
    )
    state._log_action("scheduler.source_refresh", f"{len(new)} fresh / {len(raw)} total")


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
        now = time.time()
        w = state._stats_writer()
        w.submit("DELETE FROM traffic_log WHERE ts < ?", [(now - 7 * 86400,)])
        # Hard cap on top of the time retention: a very busy week must never
        # push the table into the tens of millions of rows. The cutoff rowid
        # lookup runs on the reader connection: a stale cutoff only delays
        # pruning by one cycle, never deletes extra rows.
        try:
            conn = state._stats_db()
            row = conn.execute(
                "SELECT rowid FROM traffic_log ORDER BY rowid DESC LIMIT 1 OFFSET 2000000"
            ).fetchone()
            conn.close()
            if row is not None:
                w.submit("DELETE FROM traffic_log WHERE rowid <= ?", [(row[0],)])
        except Exception as e:
            logger.debug(f"traffic cap probe skipped: {e}")
        w.submit("DELETE FROM events WHERE ts < ?", [(now - 30 * 86400,)])
        w.submit("DELETE FROM actions WHERE ts < ?", [(now - 30 * 86400,)])
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


async def _execute_db_maintenance(state, entry: ScheduleEntry):
    """Checkpoint WALs, prune retention-exempt tables and vacuum bloated DBs.

    The WAL file grows without bound when checkpoints keep failing (e.g. a
    full disk), so every run starts with a TRUNCATE checkpoint to keep the
    file small.  Tables without their own retention (proxy_checks,
    canary_history) are pruned here.  VACUUM only runs when the freelist
    ratio passes the configured threshold and the previous vacuum is old
    enough — full VACUUM rewrites the whole file, so it is deliberately
    throttled.  Config keys: retention_days (30), vacuum_hours (168),
    freelist_pct (25).
    """
    cfg = entry.config or {}
    try:
        retention_days = max(1, int(cfg.get("retention_days", 30)))
        vacuum_hours = max(1, int(cfg.get("vacuum_hours", 168)))
        freelist_pct = max(0, min(100, int(cfg.get("freelist_pct", 25))))
    except Exception:
        logger.warning("Scheduler: db_maintenance — bad config, using defaults")
        retention_days, vacuum_hours, freelist_pct = 30, 168, 25

    state._emit("Scheduler: DB maintenance starting", "info")
    results = []
    try:
        # Nothing must be mid-flight before the checkpoint runs.
        state._flush_proxy_checks()
        state.drain_db_writers()
        now = time.time()
        w = state._stats_writer()
        w.submit("DELETE FROM proxy_checks WHERE ts < ?", [(now - retention_days * 86400,)])
        w.submit("DELETE FROM canary_history WHERE ts < ?", [(now - 90 * 86400,)])
        w.drain()
        for name, path in (("state", state._state_db_path), ("stats", state._db_path)):
            # Vacuum markers (last_vacuum_*) live in state.db's runtime_state
            # for both databases, so the stats vacuum gets the same throttle.
            marker_path = str(state._state_db_path)
            result = await asyncio.to_thread(
                _maintain_db, str(path), name, freelist_pct, vacuum_hours, marker_path
            )
            if result.get("last_vacuum"):
                state._state_writer().submit(
                    "INSERT OR REPLACE INTO runtime_state (key, value) VALUES (?, ?)",
                    [(f"last_vacuum_{name}", str(result["last_vacuum"]))],
                )
            results.append(result)
        state.drain_db_writers()
    except Exception as e:
        logger.error(f"Scheduler: db_maintenance failed: {e}")
        state._emit(f"Scheduler: DB maintenance failed: {e}", "error")
        raise

    summary = "; ".join(
        f"{r['name']}: wal {r['checkpoint_frames']} frames"
        + (f", vacuumed ({r['freelist_ratio']:.1f}% free)" if r["vacuum"] else "")
        for r in results
    )
    state._emit(f"Scheduler: DB maintenance done — {summary}", "ok")
    state._log_action("scheduler.db_maintenance", summary)


def _maintain_db(path: str, name: str, freelist_pct: int, vacuum_hours: int,
                 marker_path: str | None = None) -> dict:
    """Run checkpoint + vacuum on one SQLite file in a worker thread.

    Uses its own connection so the operation never blocks the event loop.
    Returns a summary dict; ``last_vacuum`` is set (to persist upstream) only
    when a VACUUM actually ran.  The vacuum marker is read from ``marker_path``
    (defaults to ``path``) — both markers live in state.db so the stats
    database gets the same vacuum throttle.
    """
    result = {"name": name, "checkpoint_frames": 0, "vacuum": False,
              "freelist_ratio": 0.0, "last_vacuum": 0.0}
    conn = sqlite3.connect(path, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        pages = conn.execute("PRAGMA page_count").fetchone()[0]
        free = conn.execute("PRAGMA freelist_count").fetchone()[0]
        ratio = (free / pages * 100.0) if pages else 0.0
        result["freelist_ratio"] = round(ratio, 1)
        last_vacuum = 0.0
        try:
            marker = sqlite3.connect(marker_path or path, timeout=30)
            try:
                marker.execute("PRAGMA busy_timeout=30000")
                row = marker.execute(
                    "SELECT value FROM runtime_state WHERE key=?",
                    (f"last_vacuum_{name}",),
                ).fetchone()
                if row is not None:
                    last_vacuum = float(row[0] or 0.0)
            finally:
                marker.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)
        now = time.time()
        if ratio >= freelist_pct and now - last_vacuum >= vacuum_hours * 3600:
            conn.commit()
            conn.execute("VACUUM")
            result["vacuum"] = True
            result["last_vacuum"] = now
    except Exception as e:
        logger.error(f"db maintenance failed ({name}): {e}")
        raise
    finally:
        conn.close()
    return result
