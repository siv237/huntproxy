"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.models import ProxyRating

class HuntCycleMixin:
    async def _hunt_cycle(self):
            try:
                self._canary_task = asyncio.create_task(self._canary_loop())
                self.phase = self.PHASE_DOWNLOAD
                self.phase_started = time.time()
                self._emit("Hunt started", "phase")

                raw = await self._download_sources()
                self.downloaded = len(raw)
                self._emit(f"Downloaded {len(raw)} unique candidates", "info")

                self.phase = self.PHASE_BLACKLIST
                self.phase_started = time.time()

                # Combine IP blacklist + blocklist sources into one progress
                ip_bl_sources = [s for s in self.get_ip_blacklist_sources() if s.get("enabled")]
                bl_sources = [s for s in self.get_blocklist_sources() if s.get("enabled")]
                self.bl_sources_total = len(ip_bl_sources) + len(bl_sources)
                self.bl_sources_done = 0
                self.bl_results = [
                    {"id": s["id"], "name": s.get("name", s["id"]), "status": "pending", "count": 0}
                    for s in ip_bl_sources + bl_sources
                ]
                self._emit("Downloading IP blacklists...", "info")
                ip_bl_results = await self._download_ip_blacklists()
                total_ip_bl = sum(ip_bl_results.values())
                self._emit(f"Downloaded {total_ip_bl} IP blacklist entries from {len(ip_bl_results)} sources", "info")
                # Update blacklist download progress
                for s in ip_bl_sources:
                    self.bl_sources_done += 1
                    for r in self.bl_results:
                        if r["id"] == s["id"]:
                            r["status"] = "ok" if s["id"] in ip_bl_results else "error"
                            r["count"] = ip_bl_results.get(s["id"], 0)
                            break

                self._emit("Downloading country blocklists...", "info")
                bl_results = await self._download_blocklists()
                total_bl = sum(bl_results.values())
                self._emit(f"Downloaded {total_bl} blocklist entries from {len(bl_results)} sources", "info")
                for s in bl_sources:
                    self.bl_sources_done += 1
                    for r in self.bl_results:
                        if r["id"] == s["id"]:
                            r["status"] = "ok" if s["id"] in bl_results else "error"
                            r["count"] = bl_results.get(s["id"], 0)
                            break

                self.phase = self.PHASE_VALIDATE
                self.phase_started = time.time()
                self.checking_total = len(raw)
                self.checked = 0
                self.working = 0
                self.new_working = 0
                self.confirmed_working = 0
                self.failed = 0
                self._emit(f"Validating {len(raw)} proxies...", "info")

                await self._validate_all(raw)
                self._update_source_stats()
                await self._pause_event.wait()

                self.phase = self.PHASE_HEALTH
                self.phase_started = time.time()
                self._emit(f"Initial validation done. Starting health-check loop", "info")
                self.phase = self.PHASE_DONE
                self._emit("Hunt cycle complete", "ok")
            except asyncio.CancelledError:
                self._emit("Hunt cancelled", "warn")
            except Exception as e:
                self._emit(f"Hunt error: {e}", "error")
                self.phase = self.PHASE_DONE
                logger.exception("Hunt failed")
            finally:
                # Always release the busy flag so the scheduler can start the
                # next hunt cycle. Without this, a cancelled/errored hunt would
                # leave _hunt_running=True forever and every scheduled hunt
                # would be skipped with "fetch in progress".
                self._hunt_running = False
                if self._canary_task is not None and not self._canary_task.done():
                    self._canary_task.cancel()
                self._canary_task = None
                if self.phase not in (self.PHASE_DONE, self.PHASE_IDLE):
                    self.phase = self.PHASE_DONE
                self._save_state()

    async def _auto_pause_if_internet_down(self):
            self._internet_suspect = True
            self._emit("Suspect internet down (%d/%d fast fails) — checking canary..." % (self._fail_streak, self._check_streak), "warn")
            try:
                alive = await self.is_internet_alive()
                if not alive:
                    self.pause_hunt(manual=False)
                else:
                    self._internet_suspect = False
                    self._fail_streak = 0
                    self._check_streak = 0
                    self._emit("Canary OK — failures are proxy issues, not internet", "info")
            except Exception:
                self.pause_hunt(manual=False)
