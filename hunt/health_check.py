"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.models import ProxyRating

class HealthCheckMixin:
    async def _health_check(self, manual: bool = False):
            if self._health_running:
                self._emit("Health check already in progress, skipping", "warn")
                return

            # Capture the pre-recheck state BEFORE anything changes it.
            saved_phase = self.phase
            saved_phase_started = self.phase_started
            saved_checking_total = self.checking_total
            saved_checked = self.checked
            saved_working = self.working
            saved_new_working = self.new_working
            saved_confirmed_working = self.confirmed_working
            saved_failed = self.failed
            saved_downloaded = self.downloaded
            saved_last_proxy = self.last_proxy
            saved_last_country = self.last_country
            saved_sources_total = self.sources_total
            saved_sources_done = self.sources_done
            saved_bl_total = self.bl_sources_total
            saved_bl_done = self.bl_sources_done
            saved_bl_results = list(self.bl_results)
            saved_source_status = dict(getattr(self, '_source_fetch_status', {}))
            saved_paused = self._paused
            saved_manual_pause = self._manual_pause

            # Pause the hunt if it's running and not already paused.
            hunt_task_active = bool(self.task and not self.task.done())
            if hunt_task_active and not self._paused:
                self.pause_hunt(manual=True)
                await asyncio.sleep(0.1)

            self._health_running = True
            ok_count = 0
            fail_count = 0

            try:
                candidates = [r for r in self.ratings.values()
                              if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
                if not candidates:
                    self._emit("No candidates for health check", "info")
                else:
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
                    _hctr = [0]

                    async def check(r: ProxyRating):
                        nonlocal ok_count, fail_count
                        wid = _hctr[0]; _hctr[0] += 1
                        try:
                            _p = int(r.address.rsplit(":", 1)[1])
                            _proto = "socks5" if _p in (1080, 10808, 9050) else "socks4" if _p == 4145 else "http"
                        except Exception:
                            _proto = "http"
                        self._active_checks[wid] = {"addr": r.address, "step": "queued", "started": time.time(), "protocol": _proto}
                        try:
                            async with sem:
                                if self._internet_suspect:
                                    return
                                self._active_checks[wid] = {"addr": r.address, "step": "connect", "started": time.time(), "protocol": _proto}
                                http_task = asyncio.create_task(self._check_proxy(r.address))
                                ssl_task = asyncio.create_task(self._check_ssl(r.address))
                                try:
                                    results = await asyncio.wait_for(
                                        asyncio.gather(http_task, ssl_task, return_exceptions=True),
                                        timeout=self.effective_timeout + 5,
                                    )
                                except asyncio.TimeoutError:
                                    http_task.cancel()
                                    ssl_task.cancel()
                                    results = [asyncio.TimeoutError(), asyncio.TimeoutError()]

                                if isinstance(results[0], Exception):
                                    ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = False, "", False, False, {}, {}, 0.0, "", False
                                else:
                                    ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = results[0]
                                if isinstance(results[1], Exception):
                                    ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = False, "", "", {}, 0.0, False
                                else:
                                    ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = results[1]

                                if not ok and ssl_ok:
                                    ok = True
                                    country = ssl_country
                                    cc = ssl_cc
                                    egress = ssl_egress
                                    http_latency = ssl_latency
                                    supports_connect = ssl_supports_connect
                                elif ok and ssl_ok:
                                    if not egress and ssl_egress:
                                        egress = ssl_egress
                                    if not supports_connect and ssl_supports_connect:
                                        supports_connect = ssl_supports_connect

                                if ok and not self._is_socks_addr(r.address) and not supports_connect:
                                    ok = False

                                speed = 0.0
                                if ok:
                                    self._active_checks[wid] = {"addr": r.address, "step": "speed", "started": time.time(), "protocol": _proto, "country": country, "cc": cc}
                                    host, port_str = r.address.rsplit(":", 1)
                                    is_socks = port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145)
                                    use_ssl = ssl_ok and not is_socks
                                    try:
                                        speed = await asyncio.wait_for(
                                            self._measure_speed(host, int(port_str), is_socks,
                                                                use_ssl=use_ssl, supports_connect=supports_connect),
                                            timeout=self.effective_timeout + 5,
                                        )
                                    except (asyncio.TimeoutError, Exception):
                                        speed = 0.0

                                async with lock:
                                    self.checked += 1
                                    if ok:
                                        ok_count += 1
                                        self.working = ok_count
                                        self.confirmed_working = ok_count
                                        self.last_proxy = r.address
                                        self.last_country = country
                                    else:
                                        fail_count += 1
                                        self.failed = fail_count
                                    self._update_rating(r.address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
                                    if self.checked % 10 == 0 or ok:
                                        pct = int(100 * self.checked / max(1, self.checking_total))
                                        self._emit(
                                            f"{pct}% {self.checked}/{self.checking_total} | "
                                            f"working: {ok_count} | last: {r.address} {country}",
                                            "progress"
                                        )
                        finally:
                            self._active_checks.pop(wid, None)

                    tasks = [asyncio.create_task(check(r)) for r in candidates]
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
                    self._emit(f"Health check done: {ok_count} ok, {fail_count} failed", "ok")
            finally:
                # Only restore counters/phase if we actually changed them
                # (i.e. phase is still HEALTH). If the hunt cycle advanced
                # past HEALTH while we were running, its state is authoritative.
                if self.phase == self.PHASE_HEALTH:
                    self.checking_total = saved_checking_total
                    self.checked = min(saved_checked, saved_checking_total)
                    self.working = saved_working
                    self.new_working = saved_new_working
                    self.confirmed_working = saved_confirmed_working
                    self.failed = saved_failed
                    self.downloaded = saved_downloaded
                    self.last_proxy = saved_last_proxy
                    self.last_country = saved_last_country
                    self.sources_total = saved_sources_total
                    self.sources_done = saved_sources_done
                    self.bl_sources_total = saved_bl_total
                    self.bl_sources_done = saved_bl_done
                    self.bl_results = saved_bl_results
                    self._source_fetch_status = saved_source_status
                    self.phase = saved_phase
                    self.phase_started = saved_phase_started
                self._log_action("health.restore", "counters-restored", extra={
                    "checking_total": self.checking_total,
                    "checked": self.checked,
                    "ok_count": ok_count,
                    "fail_count": fail_count,
                })

                # Resume hunt if we paused it.
                if hunt_task_active and not saved_paused:
                    self._paused = False
                    self._manual_pause = False
                    self._internet_suspect = False
                    self._fail_streak = 0
                    self._check_streak = 0
                    self._pause_event.set()
                    self._emit("Hunt RESUMED", "ok")

                self._health_running = False
                self._health_manual = False
                self._health_task = None

    async def _revalidate_stale_proxies(self):
            """Re-check proxies that are stale at startup.

            Any alive proxy whose last check is older than an hour is re-checked.
            """
            now = time.time()
            stale_threshold = now - 3600
            candidates = []
            for addr in list(self.ratings.keys()):
                r = self.ratings[addr]
                if r.in_blacklist:
                    continue
                if r.last_check < stale_threshold:
                    candidates.append(r)
            if not candidates:
                return
            self._emit(f"Re-validating {len(candidates)} stale proxies at startup", "info")
            sem = asyncio.Semaphore(self.health_parallel)
            lock = asyncio.Lock()
            ok_count = fail_count = 0

            async def check(r: ProxyRating):
                nonlocal ok_count, fail_count
                async with sem:
                    http_task = asyncio.create_task(self._check_proxy(r.address))
                    ssl_task = asyncio.create_task(self._check_ssl(r.address))
                    results = await asyncio.gather(http_task, ssl_task, return_exceptions=True)
                    if isinstance(results[0], Exception):
                        ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = False, "", False, False, {}, {}, 0.0, "", False
                    else:
                        ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = results[0]
                    if isinstance(results[1], Exception):
                        ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = False, "", "", {}, 0.0, False
                    else:
                        ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = results[1]
                    if not ok and ssl_ok:
                        ok = True
                        country = ssl_country
                        cc = ssl_cc
                        egress = ssl_egress
                        http_latency = ssl_latency
                        supports_connect = ssl_supports_connect
                    elif ok and ssl_ok:
                        if not egress and ssl_egress:
                            egress = ssl_egress
                        if not supports_connect and ssl_supports_connect:
                            supports_connect = ssl_supports_connect
                    # Non-SOCKS proxies must support CONNECT to be useful for HTTPS.
                    if ok and not self._is_socks_addr(r.address) and not supports_connect:
                        ok = False
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
                            ok_count += 1
                            self._fail_streak = 0
                        else:
                            fail_count += 1
                            self._fail_streak += 1
                        self._update_rating(r.address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)

            tasks = [asyncio.create_task(check(r)) for r in candidates]
            await asyncio.gather(*tasks, return_exceptions=True)
            self._save_state()
            self._save_working_file()
            self._rating_updates_since_save = 0
            self._emit(f"Startup re-validation done: {ok_count} ok, {fail_count} failed", "ok")

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
