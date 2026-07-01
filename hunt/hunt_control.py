"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.models import ProxyRating

class HuntControlMixin:
    def start_hunt(self) -> bool:
            if self.phase not in (self.PHASE_IDLE, self.PHASE_DONE):
                return False
            if getattr(self, '_health_running', False):
                return False
            self._paused = False
            self._manual_pause = False
            self._internet_suspect = False
            self._fail_streak = 0
            self._check_streak = 0
            self._pause_event.set()
            self._hunt_running = True
            try:
                loop = asyncio.get_running_loop()
                self.task = loop.create_task(self._hunt_cycle())
                return True
            except RuntimeError:
                self._hunt_running = False
                return False

    def stop_health(self):
            """Abort a running health-check recheck, cancelling its task."""
            if self._health_task and not self._health_task.done():
                self._health_task.cancel()
            self._health_task = None
            self._active_checks.clear()
            self._emit("Health check aborted by user", "warn")

    def stop_hunt(self):
            if self.task and not self.task.done():
                self.task.cancel()
            if self._canary_task and not self._canary_task.done():
                self._canary_task.cancel()
                self._canary_task = None
            self._paused = False
            self._manual_pause = False
            self._pause_event.set()
            self.phase = self.PHASE_IDLE
            self._hunt_running = False
            self._save_state()
            self._save_working_file()
            self._emit("Hunt stopped by user", "warn")

    def pause_hunt(self, manual: bool = True) -> bool:
            if self._paused or not self.task or self.task.done():
                return False
            self._paused = True
            self._manual_pause = manual
            self._pause_event.clear()
            self._phase_before_pause = self.phase
            self.phase = self.PHASE_PAUSED
            self.phase_started = time.time()
            self._emit("Hunt PAUSED (%s)" % ("manually" if manual else "internet down"), "warn")
            return True

    def resume_hunt(self, manual: bool = False) -> bool:
            if not self._paused:
                return False
            if self._manual_pause and not manual:
                return False
            self._paused = False
            self._manual_pause = False
            self._internet_suspect = False
            self._fail_streak = 0
            self._check_streak = 0
            self._pause_event.set()
            if self.phase == self.PHASE_PAUSED:
                self.phase = self._phase_before_pause
                self.phase_started = time.time()
            self._emit("Hunt RESUMED", "ok")
            return True

    def skip_phase(self) -> bool:
            """Abort the current download/blacklist/validation phase and let the
            hunt cycle continue with whatever has been collected so far."""
            if not self.task or self.task.done():
                return False
            if self.phase not in (self.PHASE_DOWNLOAD, self.PHASE_BLACKLIST, self.PHASE_VALIDATE):
                return False
            self._skip_requested = True
            self._skip_event.set()
            self._emit(f"Skipping {self.phase} phase...", "warn")
            return True

    def _reset_skip(self):
            self._skip_requested = False
            try:
                self._skip_event.clear()
            except Exception:
                pass

    async def _kill_active_downloads(self):
            procs = getattr(self, '_active_dl_procs', None)
            if not procs:
                return
            for p in procs:
                try:
                    p.kill()
                except Exception:
                    pass
            self._active_dl_procs = []

    async def _gather_skip_aware(self, tasks):
            """Await ``gather(tasks, return_exceptions=True)``.

            If a skip was requested via :meth:`skip_phase`, pending tasks are
            cancelled, in-flight download subprocesses are killed and an empty
            list is returned so the caller can proceed to the next phase.
            """
            gather_task = asyncio.ensure_future(asyncio.gather(*tasks, return_exceptions=True))
            skip_task = asyncio.ensure_future(self._skip_event.wait())
            done, _pending = await asyncio.wait(
                {gather_task, skip_task}, return_when=asyncio.FIRST_COMPLETED,
            )
            if skip_task in done and not gather_task.done():
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await self._kill_active_downloads()
                try:
                    await gather_task
                except Exception:
                    pass
                self._reset_skip()
                return []
            skip_task.cancel()
            return gather_task.result()
