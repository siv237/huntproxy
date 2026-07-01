"""Scheduler API methods — extracted from scheduler.py."""
import time
from hunt.schedule_entry import ScheduleEntry, TASK_TYPES

class SchedulerApiMixin:
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

