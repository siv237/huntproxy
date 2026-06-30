"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.models import ProxyRating

class HealthMixin:
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

    async def _canary_loop(self):
            while True:
                await asyncio.sleep(15)
                try:
                    was_paused = self._paused
                    result = await self._check_canary()
                    if not result["alive"] and not self._paused:
                        self.pause_hunt(manual=False)
                    elif result["alive"] and self._paused and not self._manual_pause:
                        self.resume_hunt(manual=False)
                except asyncio.CancelledError:
                    return
                except Exception:
                    pass

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

    async def _check_canary(self) -> dict:
            hosts = self.canary_hosts or ["ya.ru", "google.com", "2ip.ru"]
            results = {}
            latencies = {}
            canary_to = 25 if self._channel_is_set() else 8
            for host in hosts:
                t0 = time.monotonic()
                try:
                    reader, writer = await self._outbound_connect(host, 443, timeout=canary_to)
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                    lat = int((time.monotonic() - t0) * 1000)
                    results[host] = True
                    latencies[host] = lat
                except Exception:
                    results[host] = False
                    latencies[host] = -1
            alive_count = sum(1 for v in results.values() if v)
            total = len(results)
            was_alive = self._internet_alive
            alive = alive_count > total // 2
            self._internet_alive = alive
            self._canary_last_check = time.time()

            if was_alive is True and not alive:
                self._emit("Internet DOWN — all canary hosts unreachable", "error")
            elif was_alive is False and alive:
                self._emit("Internet RESTORED — canary hosts reachable", "ok")

            direct_ip = ""
            direct_country = ""
            direct_isp = ""
            direct_city = ""
            if alive:
                try:
                    reader, writer = await self._outbound_connect("ip-api.com", 80, timeout=canary_to)
                    req = "GET /json/?fields=query,country,isp,city HTTP/1.1\r\nHost: ip-api.com\r\nConnection: close\r\n\r\n"
                    writer.write(req.encode()); await writer.drain()
                    resp = b""
                    while True:
                        chunk = await asyncio.wait_for(reader.read(4096), timeout=5)
                        if not chunk: break
                        resp += chunk
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass
                    body_start = resp.find(b"\r\n\r\n")
                    if body_start >= 0:
                        import json as _json
                        data = _json.loads(resp[body_start+4:])
                        new_ip = data.get("query", "")
                        new_country = data.get("country", "")
                        new_isp = data.get("isp", "")
                        new_city = data.get("city", "")
                        old_ip = self._canary_last_ip if hasattr(self, '_canary_last_ip') else ""
                        if old_ip and new_ip and old_ip != new_ip:
                            self._emit(f"ISP changed: {old_ip} ({getattr(self, '_canary_last_isp', '')}) → {new_ip} ({new_isp})", "warn")
                        direct_ip = new_ip
                        direct_country = new_country
                        direct_isp = new_isp
                        direct_city = new_city
                        self._canary_last_ip = new_ip
                        self._canary_last_isp = new_isp
                        self._canary_last_country = new_country
                        self._canary_last_city = new_city
                except Exception:
                    pass

            try:
                conn = self._stats_db()
                conn.execute(
                    "INSERT INTO canary_history (ts, alive, alive_count, total_count, host_results, direct_ip, direct_country, direct_isp, direct_city) VALUES (?,?,?,?,?,?,?,?,?)",
                    (time.time(), 1 if alive else 0, alive_count, total,
                     json.dumps(results), direct_ip, direct_country, direct_isp, direct_city)
                )
                conn.commit()
                conn.close()
            except Exception:
                pass

            result = {
                "alive": alive,
                "hosts": results,
                "latencies": latencies,
                "alive_count": alive_count,
                "total": total,
                "direct_ip": direct_ip,
                "direct_country": direct_country,
                "direct_isp": direct_isp,
                "direct_city": direct_city,
            }
            self._canary_cache = result
            return result

    async def is_internet_alive(self) -> bool:
            if self._internet_alive is not None and (time.time() - self._canary_last_check) < self._canary_interval:
                return self._internet_alive
            result = await self._check_canary()
            return result["alive"]

    def get_canary_status(self) -> dict:
            if self._canary_cache:
                result = dict(self._canary_cache)
                result["channel"] = self.get_channel_status()
                return result
            return {
                "alive": self._internet_alive,
                "hosts": {},
                "latencies": {},
                "alive_count": 0,
                "total": len(self.canary_hosts),
                "last_check": self._canary_last_check,
                "canary_hosts": self.canary_hosts,
                "direct_ip": getattr(self, '_canary_last_ip', ''),
                "direct_country": getattr(self, '_canary_last_country', ''),
                "direct_isp": getattr(self, '_canary_last_isp', ''),
                "direct_city": getattr(self, '_canary_last_city', ''),
                "channel": self.get_channel_status(),
            }

    def set_canary_hosts(self, hosts: list):
            self.canary_hosts = hosts
            self._internet_alive = None
            self._emit(f"Canary hosts updated: {', '.join(hosts)}", "info")

    def get_canary_history(self, hours: int = 24) -> list:
            try:
                conn = self._stats_db()
                since = time.time() - hours * 3600
                rows = conn.execute(
                    "SELECT ts, alive, alive_count, total_count, host_results, direct_ip, direct_country, direct_isp, direct_city "
                    "FROM canary_history WHERE ts>? ORDER BY ts ASC", (since,)
                ).fetchall()
                conn.close()
                result = []
                for r in rows:
                    entry = dict(r)
                    try:
                        entry["host_results"] = json.loads(entry.get("host_results", "{}"))
                    except Exception:
                        entry["host_results"] = {}
                    result.append(entry)
                return result
            except Exception as e:
                logger.error("get_canary_history: %s", e)
                return []

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
              2. a fresh full hunt cycle — read lists → blacklists → validate
                 new candidates

            Re-validation is NOT a hunt: it does not set _hunt_running, so the
            scheduler's proxy_check task is free to run concurrently.
            """
            # The restored _hunt_running flag is stale (no live task survived
            # the restart) — clear it so the scheduler is not blocked.
            self._hunt_running = False
            self._save_state()

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
