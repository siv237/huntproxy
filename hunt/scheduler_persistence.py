"""Scheduler persistence methods — extracted from scheduler.py."""
import json
from hunt.constants import logger
from hunt.schedule_entry import ScheduleEntry, DEFAULT_SCHEDULES, TASK_TYPES

class SchedulerPersistenceMixin:
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

