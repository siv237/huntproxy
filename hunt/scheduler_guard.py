"""Bulk task cancellation and the scheduler internet gate.

Extracted from scheduler.py to keep that module under the size budget.  The
mixin operates on the SchedulerEngine's planning state (``_running_tasks``,
``_queue``, ``_paused``) and is intentionally free of execution logic.
"""

import asyncio
import time

from hunt.schedule_entry import TASK_TYPES


class SchedulerGuardMixin:
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

    def _respect_internet_types(self) -> set[str]:
        """Task types that perform network checks and must not run offline."""
        return {tt for tt, d in TASK_TYPES.items() if d.get("respect_internet")}

    async def cancel_all(self, reason: str = "cancelled") -> list[str]:
        """Cancel every running task and clear the pending queue.

        Returns the list of cancelled task types.  Used by the manual Start
        Hunt path (strict operator semantics) and by the internet gate.
        """
        running = dict(self._running_tasks)
        self._queue.clear()
        for t in running.values():
            if not t.done():
                t.cancel()
        if running:
            await asyncio.gather(*running.values(), return_exceptions=True)
        self._running_tasks.clear()
        now = time.time()
        for entry in self._schedules.values():
            if entry.last_status in ("running", "queued"):
                entry.last_status = "cancelled"
                entry.last_error = reason
                entry.next_run = now + entry.interval_sec
                self._persist(entry)
        if running:
            self.state._emit(
                f"Scheduler: cancelled {len(running)} running task(s) — {reason}",
                "warn",
            )
        return list(running.keys())

    async def _cancel_check_tasks(self) -> list[str]:
        """Cancel only the running network-check tasks (respect_internet)."""
        types = self._respect_internet_types()
        running = {tt: t for tt, t in self._running_tasks.items() if tt in types}
        for t in running.values():
            if not t.done():
                t.cancel()
        if running:
            await asyncio.gather(*running.values(), return_exceptions=True)
            for tt in running:
                self._running_tasks.pop(tt, None)
        return list(running.keys())

    async def _internet_gate(self) -> None:
        """Pause all network checking while the internet is unreachable.

        A machine that has lost connectivity for hours must not keep spawning
        proxy checks — every attempt would fail and pile up errors.  When the
        canary reports the internet down, the scheduler pauses and all running
        check tasks are cancelled; when connectivity returns, it resumes and
        the due tasks run again.  A manual/user pause (or the exclusive
        manual-hunt pause) is never overridden.
        """
        if self._stopped:
            return
        if self._paused and not self._paused_by_internet:
            return
        try:
            alive = await self.state.is_internet_alive()
        except Exception:
            alive = False
        if not alive:
            if not self._paused_by_internet:
                self._paused_by_internet = True
                self.pause_all()
                cancelled = await self._cancel_check_tasks()
                self.state._emit(
                    "Internet DOWN — scheduler paused, checks stopped"
                    + (f" (cancelled: {', '.join(cancelled)})" if cancelled else ""),
                    "warn",
                )
        elif self._paused_by_internet:
            self._paused_by_internet = False
            self.resume_all()
