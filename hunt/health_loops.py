"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.models import ProxyRating

class HealthLoopsMixin:
    async def _health_loop(self):
            while True:
                await asyncio.sleep(self.health_interval)
                try:
                    if self._paused:
                        await self._pause_event.wait()
                        continue
                    internet_ok = await self.is_internet_alive()
                    if not internet_ok:
                        self.pause_hunt(manual=False)
                        continue
                    await self._health_check()
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    self._emit(f"Health check error: {e}", "error")

    async def _ip_blacklist_loop(self):
            """Periodic refresh of downloaded IP blacklists."""
            while True:
                await asyncio.sleep(self.ip_blacklist_fetch_interval)
                try:
                    if not self.ip_blacklist_enabled:
                        continue
                    if self._paused:
                        await self._pause_event.wait()
                        continue
                    internet_ok = await self.is_internet_alive()
                    if not internet_ok:
                        continue
                    if getattr(self, '_fetching_ip_blacklists', False):
                        continue
                    self._emit("Refreshing IP blacklists...", "info")
                    results = await self._download_ip_blacklists()
                    total = sum(results.values())
                    self._emit(f"Refreshed {total} IP blacklist entries", "info")
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    self._emit(f"IP blacklist refresh error: {e}", "error")

    async def _history_loop(self):
            while True:
                await asyncio.sleep(60)
                try:
                    self._push_history()
                except Exception:
                    pass
                try:
                    conn = self._stats_db()
                    cutoff_traffic = time.time() - 7 * 86400
                    cutoff_events = time.time() - 30 * 86400
                    conn.execute("DELETE FROM traffic_log WHERE ts < ?", (cutoff_traffic,))
                    conn.execute("DELETE FROM events WHERE ts < ?", (cutoff_events,))
                    conn.execute("DELETE FROM actions WHERE ts < ?", (cutoff_events,))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
