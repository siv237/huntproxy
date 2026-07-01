"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.models import ProxyRating


class _HealthContext:
    """Shared state for a single _health_check run."""
    def __init__(self):
        self.ok_count = 0
        self.fail_count = 0
        self.ctr = 0


class HealthCheckMixin:
    async def _health_check(self, manual: bool = False):
        if self._health_running:
            self._emit("Health check already in progress, skipping", "warn")
            return

        saved = self._save_health_state()
        hunt_task_active = bool(self.task and not self.task.done())
        if hunt_task_active and not self._paused:
            self.pause_hunt(manual=True)
            await asyncio.sleep(0.1)

        self._health_running = True
        ctx = _HealthContext()

        try:
            candidates = [r for r in self.ratings.values()
                          if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
            if not candidates:
                self._emit("No candidates for health check", "info")
            else:
                await self._run_health_checks(candidates, manual, ctx)
        finally:
            self._restore_health_state(saved, hunt_task_active, ctx)
            self._health_running = False
            self._save_state()

    def _save_health_state(self) -> dict:
        return {
            "phase": self.phase,
            "phase_started": self.phase_started,
            "checking_total": self.checking_total,
            "checked": self.checked,
            "working": self.working,
            "new_working": self.new_working,
            "confirmed_working": self.confirmed_working,
            "failed": self.failed,
            "downloaded": self.downloaded,
            "last_proxy": self.last_proxy,
            "last_country": self.last_country,
            "sources_total": self.sources_total,
            "sources_done": self.sources_done,
            "bl_total": self.bl_sources_total,
            "bl_done": self.bl_sources_done,
            "bl_results": list(self.bl_results),
            "source_status": dict(getattr(self, '_source_fetch_status', {})),
            "paused": self._paused,
            "manual_pause": self._manual_pause,
        }

    async def _run_health_checks(self, candidates, manual, ctx):
        self.phase = self.PHASE_HEALTH
        self._health_manual = manual
        self.phase_started = time.time()
        self.checking_total = len(candidates)
        self.checked = 0
        self.working = 0
        self.new_working = 0
        self.confirmed_working = 0
        self.failed = 0
        self._fail_streak = 0
        self._check_streak = 0
        self._emit(f"Health-checking {len(candidates)} alive proxies", "info")
        self._log_action("health.begin", f"{len(candidates)} candidates")

        sem = asyncio.Semaphore(self.health_parallel)
        lock = asyncio.Lock()
        tasks = [asyncio.create_task(self._health_check_one(r, sem, lock, ctx)) for r in candidates]
        overall_timeout = len(candidates) * (self.effective_timeout + 10) // max(1, self.health_parallel) + 30
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=overall_timeout,
            )
        except asyncio.TimeoutError:
            for t in tasks:
                if not t.done():
                    t.cancel()
            self._emit("Health check timed out, cancelling stuck tasks", "warn")
        except asyncio.CancelledError:
            for t in tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._save_state()
            self._save_working_file()
            self._emit("Health check aborted", "warn")
            raise

        self._save_state()
        self._save_working_file()
        self._rating_updates_since_save = 0
        self._push_history()
        self._emit(f"Health check done: {ctx.ok_count} ok, {ctx.fail_count} failed", "ok")

    def _restore_health_state(self, saved, hunt_task_active, ctx):
        if self.phase == self.PHASE_HEALTH:
            self.checking_total = saved["checking_total"]
            self.checked = min(saved["checked"], saved["checking_total"])
            self.working = saved["working"]
            self.new_working = saved["new_working"]
            self.confirmed_working = saved["confirmed_working"]
            self.failed = saved["failed"]
            self.downloaded = saved["downloaded"]
            self.last_proxy = saved["last_proxy"]
            self.last_country = saved["last_country"]
            self.sources_total = saved["sources_total"]
            self.sources_done = saved["sources_done"]
            self.bl_sources_total = saved["bl_total"]
            self.bl_sources_done = saved["bl_done"]
            self.bl_results = saved["bl_results"]
            self._source_fetch_status = saved["source_status"]
            self.phase = saved["phase"]
            self.phase_started = saved["phase_started"]
        self._log_action("health.restore", "counters-restored", extra={
            "checking_total": self.checking_total,
            "checked": self.checked,
            "ok_count": ctx.ok_count,
            "fail_count": ctx.fail_count,
        })
        if hunt_task_active and not saved["paused"]:
            self._paused = False
            self._manual_pause = False
            self._internet_suspect = False
            self._fail_streak = 0
            self._check_streak = 0
            self._pause_event.set()
            self._emit("Hunt RESUMED", "ok")

    async def _health_check_one(self, r: ProxyRating, sem, lock, ctx: _HealthContext):
        wid = ctx.ctr; ctx.ctr += 1
        _proto = self._detect_protocol(r.address)
        self._active_checks[wid] = {"addr": r.address, "step": "queued", "started": time.time(), "protocol": _proto}
        try:
            async with sem:
                if self._internet_suspect:
                    return
                self._active_checks[wid] = {"addr": r.address, "step": "connect", "started": time.time(), "protocol": _proto}
                results = await self._gather_health_results(r)
                merged = self._merge_check_results(results, r.address)
                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, ssl_ok, _, _ = (
                    merged["ok"], merged["country"], merged["supports_connect"],
                    merged["mitm_suspect"], merged["egress"], merged["listen"],
                    merged["http_latency"], merged["cc"], merged["ssl_ok"],
                    merged["ssl_egress"], merged["ssl_supports_connect"],
                )
                speed = await self._measure_health_speed(r, ok, _proto, country, cc, ssl_ok, supports_connect)
                async with lock:
                    self.checked += 1
                    if ok:
                        ctx.ok_count += 1
                        self.working = ctx.ok_count
                        self.confirmed_working = ctx.ok_count
                        self.last_proxy = r.address
                        self.last_country = country
                    else:
                        ctx.fail_count += 1
                        self.failed = ctx.fail_count
                    self._update_rating(r.address, ok, country, http_latency, supports_connect,
                                        mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
                    if self.checked % 10 == 0 or ok:
                        pct = int(100 * self.checked / max(1, self.checking_total))
                        self._emit(
                            f"{pct}% {self.checked}/{self.checking_total} | "
                            f"working: {ctx.ok_count} | last: {r.address} {country}",
                            "progress"
                        )
        finally:
            self._active_checks.pop(wid, None)

    async def _gather_health_results(self, r):
        http_task = asyncio.create_task(self._check_proxy(r.address))
        ssl_task = asyncio.create_task(self._check_ssl(r.address))
        try:
            return await asyncio.wait_for(
                asyncio.gather(http_task, ssl_task, return_exceptions=True),
                timeout=self.effective_timeout + 5,
            )
        except asyncio.TimeoutError:
            http_task.cancel()
            ssl_task.cancel()
            return [asyncio.TimeoutError(), asyncio.TimeoutError()]

    async def _measure_health_speed(self, r, ok, _proto, country, cc, ssl_ok, supports_connect) -> float:
        if not ok:
            return 0.0
        wid = None
        for k, v in self._active_checks.items():
            if v.get("addr") == r.address:
                wid = k
                break
        if wid is not None:
            self._active_checks[wid] = {"addr": r.address, "step": "speed", "started": time.time(), "protocol": _proto, "country": country, "cc": cc}
        host, port_str = r.address.rsplit(":", 1)
        is_socks = port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145)
        use_ssl = ssl_ok and not is_socks
        try:
            return await asyncio.wait_for(
                self._measure_speed(host, int(port_str), is_socks,
                                    use_ssl=use_ssl, supports_connect=supports_connect),
                timeout=self.effective_timeout + 5,
            )
        except (asyncio.TimeoutError, Exception):
            return 0.0

    async def _revalidate_stale_proxies(self):
        """Re-check proxies that are stale at startup.

        Any alive proxy whose last check is older than an hour is re-checked.
        """
        now = time.time()
        stale_threshold = now - 3600
        candidates = [r for r in self.ratings.values()
                      if not r.in_blacklist and r.last_check < stale_threshold]
        if not candidates:
            return
        self._emit(f"Re-validating {len(candidates)} stale proxies at startup", "info")
        sem = asyncio.Semaphore(self.health_parallel)
        lock = asyncio.Lock()
        ctx = _HealthContext()

        tasks = [asyncio.create_task(self._revalidate_one(r, sem, lock, ctx)) for r in candidates]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._save_state()
        self._save_working_file()
        self._rating_updates_since_save = 0
        self._emit(f"Startup re-validation done: {ctx.ok_count} ok, {ctx.fail_count} failed", "ok")

    async def _revalidate_one(self, r: ProxyRating, sem, lock, ctx: _HealthContext):
        async with sem:
            results = await asyncio.gather(
                asyncio.create_task(self._check_proxy(r.address)),
                asyncio.create_task(self._check_ssl(r.address)),
                return_exceptions=True,
            )
            merged = self._merge_check_results(results, r.address)
            ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, ssl_ok, _, _ = (
                merged["ok"], merged["country"], merged["supports_connect"],
                merged["mitm_suspect"], merged["egress"], merged["listen"],
                merged["http_latency"], merged["cc"], merged["ssl_ok"],
                merged["ssl_egress"], merged["ssl_supports_connect"],
            )
            speed = 0.0
            if ok:
                host, port_str = r.address.rsplit(":", 1)
                is_socks = port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145)
                use_ssl = ssl_ok and not is_socks
                try:
                    speed = await self._measure_speed(host, int(port_str), is_socks,
                                                       use_ssl=use_ssl, supports_connect=supports_connect)
                except Exception:
                    speed = 0.0
            async with lock:
                self._check_streak += 1
                if ok:
                    ctx.ok_count += 1
                    self._fail_streak = 0
                else:
                    ctx.fail_count += 1
                    self._fail_streak += 1
                self._update_rating(r.address, ok, country, http_latency, supports_connect,
                                    mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)

    async def run_startup_cycle(self):
            """Run the startup check cycle as a background task.

            The cycle is:

              1. re-validate previously-working (stale) proxies
              2. a fresh full hunt cycle — read lists → blocklists → validate
                 new candidates

            Both phases use the shared self.checked / self.checking_total /
            self._active_checks counters, so _hunt_running must stay True for
            the ENTIRE cycle to prevent the scheduler's proxy_check from
            launching a concurrent _validate_all that double-counts progress.
            """
            # Block scheduler proxy_check for the entire startup cycle —
            # revalidation and hunt both use the same shared counters.
            self._hunt_running = True
            self._save_state()

            try:
                self._emit("Startup cycle: re-validating previously-working proxies", "phase")
                try:
                    await self._revalidate_stale_proxies()
                except Exception as e:
                    logger.error(f"Startup re-validation failed: {e}")

                self._emit("Startup cycle: starting full hunt (read lists → validate)", "phase")
                # Always start a fresh hunt cycle on restart.
                if self.task is not None and not self.task.done():
                    self.stop_hunt()
                self.phase = self.PHASE_IDLE
                if not self.start_hunt():
                    logger.warning("Could not start startup hunt cycle")
                    self._emit("Startup cycle: could not start hunt", "error")
                    return

                deadline = time.time() + 7200  # 2h safety cap
                while self.task is not None and not self.task.done():
                    if time.time() > deadline:
                        logger.error("Startup hunt cycle exceeded 2 hours")
                        self._emit("Startup cycle: hunt exceeded 2h cap", "warn")
                        break
                    await asyncio.sleep(2)
                self._emit("Startup cycle complete", "ok")
            except asyncio.CancelledError:
                self._emit("Startup cycle cancelled", "warn")
                raise
            except Exception as e:
                logger.error(f"Startup cycle error: {e}")
                self._emit(f"Startup cycle error: {e}", "error")
            finally:
                # Always release the busy flag — covers normal completion,
                # cancellation, and GC destruction (GeneratorExit). Without
                # this, a destroyed/cancelled startup cycle would leave
                # _hunt_running=True forever, blocking proxy_check forever.
                self._hunt_running = False
                self._save_state()
