"""Manual (operator-driven) Hunt start — strict interrupt-and-restart.

Extracted from hunt_control.py to keep that module under the size budget.
The Start Hunt button is authoritative: it stops every running activity,
resets the shared progress counters and begins a fresh exclusive hunt.
"""

import asyncio
import time

from hunt.constants import logger


class ManualHuntMixin:
    def _reset_progress(self):
        """Zero every shared progress counter so a fresh run starts at 0."""
        self.checked = 0
        self.checking_total = 0
        self.working = 0
        self.new_working = 0
        self.confirmed_working = 0
        self.failed = 0
        self.downloaded = 0
        self.sources_total = 0
        self.sources_done = 0
        self.bl_sources_total = 0
        self.bl_sources_done = 0
        self.bl_results = []
        self._active_checks.clear()
        self._fail_streak = 0
        self._check_streak = 0
        self._reset_skip()

    async def manual_start_hunt(self) -> bool:
        """Hard manual start: interrupt all running work and begin afresh.

        Aborts any running health recheck, cancels every scheduler task, stops
        and awaits a previous hunt, resets the shared progress counters and
        starts a new hunt cycle.  The scheduler stays paused for the whole
        manual hunt (exclusive mode) and is resumed by the hunt cycle when it
        finishes.  Refuses to start while the internet is unreachable.
        """
        try:
            alive = await self.is_internet_alive()
        except Exception:
            alive = False
        if not alive:
            self._emit("Hunt not started — no internet", "warn")
            self._log_action("hunt.start", "no-internet")
            return False

        # Abort a running health recheck (manual or scheduled) and wait for it
        # to unwind so its finally cannot clobber the reset counters.
        if self._health_task is not None and not self._health_task.done():
            self._health_task.cancel()
            try:
                await self._health_task
            except (asyncio.CancelledError, Exception):
                logger.debug("suppressed", exc_info=True)
        self._health_task = None
        self._health_running = False

        # Stop and await the previous hunt so its finally block cannot
        # overwrite the counters after we reset them.
        if self.task is not None and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                logger.debug("suppressed", exc_info=True)
        self.task = None

        # Interrupt every scheduler task and hold the scheduler paused for the
        # duration of this manual hunt.
        if self.scheduler is not None:
            self.scheduler.pause_all()
            await self.scheduler.cancel_all("manual hunt")
            self._scheduler_paused_by_hunt = True

        self._reset_progress()
        self.phase = self.PHASE_IDLE
        self.phase_started = time.time()
        self._paused = False
        self._manual_pause = False
        self._internet_suspect = False
        self._pause_event.set()
        self._hunt_running = False
        self._save_state()
        return self.start_hunt()

    def _end_manual_hunt(self):
        """Release the exclusive scheduler pause held by a manual hunt."""
        if not getattr(self, "_scheduler_paused_by_hunt", False):
            return
        self._scheduler_paused_by_hunt = False
        if self.scheduler is not None:
            self.scheduler.resume_all()
