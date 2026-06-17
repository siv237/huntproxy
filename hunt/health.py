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
            self.phase = self._phase_before_pause
            self.phase_started = time.time()
            self._emit("Hunt RESUMED", "ok")
            return True

    async def _hunt_cycle(self):
            try:
                self._canary_task = asyncio.create_task(self._canary_loop())
                self.phase = self.PHASE_DOWNLOAD
                self.phase_started = time.time()
                self._emit("Hunt started", "phase")

                raw = await self._download_sources()
                self.downloaded = len(raw)
                self._emit(f"Downloaded {len(raw)} unique candidates", "info")

                self._emit("Downloading IP blacklists...", "info")
                ip_bl_results = await self._download_ip_blacklists()
                total_ip_bl = sum(ip_bl_results.values())
                self._emit(f"Downloaded {total_ip_bl} IP blacklist entries from {len(ip_bl_results)} sources", "info")

                self.phase = self.PHASE_VALIDATE
                self.phase_started = time.time()
                self.checking_total = len(raw)
                self.checked = 0
                self.working = 0
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

                asyncio.create_task(self._health_loop())
            except asyncio.CancelledError:
                self._emit("Hunt cancelled", "warn")
            except Exception as e:
                self._emit(f"Hunt error: {e}", "error")
                self.phase = self.PHASE_DONE
                logger.exception("Hunt failed")

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
            for host in hosts:
                t0 = time.monotonic()
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, 443), timeout=5)
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
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection("ip-api.com", 80), timeout=5)
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
                return self._canary_cache
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
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    async def _health_check(self):
            # Only manual blacklist is a hard exclusion; IP-blacklisted proxies
            # remain candidates and are ranked by their reduced score.
            candidates = [r for r in self.ratings.values()
                          if r.last_status == "ok" and not r.in_blacklist]
            if not candidates:
                return
            self.phase = self.PHASE_HEALTH
            self.phase_started = time.time()
            self.checking_total = len(candidates)
            self.checked = 0
            self.working = 0
            self.failed = 0
            self._fail_streak = 0
            self._check_streak = 0
            self._emit(f"Health-checking {len(candidates)} alive proxies", "info")

            sem = asyncio.Semaphore(self.health_parallel)
            lock = asyncio.Lock()
            ok_count = fail_count = 0

            async def check(r: ProxyRating):
                nonlocal ok_count, fail_count
                while True:
                    if self._paused:
                        await self._pause_event.wait()
                    async with sem:
                        if self._internet_suspect:
                            await self._pause_event.wait()
                            continue
                        http_task = asyncio.create_task(self._check_proxy(r.address))
                        ssl_task = asyncio.create_task(self._check_ssl(r.address))
                        results = await asyncio.gather(http_task, ssl_task, return_exceptions=True)
                        if isinstance(results[0], Exception):
                            ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = False, "", False, False, {}, {}, 0.0, "", False
                        else:
                            ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = results[0]
                        if isinstance(results[1], Exception):
                            ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency = False, "", "", {}, 0.0
                        else:
                            ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency = results[1]
                        if fast_fail and not ok and not ssl_ok:
                            async with lock:
                                self._fail_streak += 1
                                self._check_streak += 1
                                if self._check_streak >= 3 and self._fail_streak / self._check_streak > 0.7:
                                    await self._auto_pause_if_internet_down()
                            if self._internet_suspect:
                                await self._pause_event.wait()
                                continue
                            return
                        if not ok and ssl_ok:
                            ok = True
                            country = ssl_country
                            cc = ssl_cc
                            egress = ssl_egress
                            http_latency = ssl_latency
                        elif ok and ssl_ok:
                            if not egress and ssl_egress:
                                egress = ssl_egress
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
                            if self._internet_suspect:
                                await self._pause_event.wait()
                                continue
                            self.checked += 1
                            self._check_streak += 1
                            if ok:
                                ok_count += 1
                                self.working = ok_count
                                self._fail_streak = 0
                            else:
                                fail_count += 1
                                self.failed = fail_count
                                self._fail_streak += 1
                            self._update_rating(r.address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
                            if self._check_streak >= 10 and self._fail_streak / self._check_streak > 0.7:
                                await self._auto_pause_if_internet_down()
                        return

            tasks = [asyncio.create_task(check(r)) for r in candidates]
            await asyncio.gather(*tasks, return_exceptions=True)
            self._save_state()
            self._save_working_file()
            self._rating_updates_since_save = 0
            self._push_history()
            self._emit(f"Health check done: {ok_count} ok, {fail_count} failed", "ok")
            self.phase = self.PHASE_DONE

    async def _revalidate_stale_proxies(self):
        """Re-check proxies that are stale at startup.

        Proxies from the main working.txt list are re-checked if the file is
        older than an hour. Any other alive proxy whose last check is older
        than an hour is also re-checked.
        """
        now = time.time()
        stale_threshold = now - 3600
        candidates = []
        loaded = getattr(self, '_working_file_loaded', set())
        loaded_mtime = getattr(self, '_working_file_mtime', now)
        working_file_stale = now - loaded_mtime > 3600
        for addr in list(self.ratings.keys()):
            r = self.ratings[addr]
            if r.in_blacklist:
                continue
            if r.last_check < stale_threshold:
                candidates.append(r)
            elif working_file_stale and addr in loaded:
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
                    ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency = False, "", "", {}, 0.0
                else:
                    ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency = results[1]
                if not ok and ssl_ok:
                    ok = True
                    country = ssl_country
                    cc = ssl_cc
                    egress = ssl_egress
                    http_latency = ssl_latency
                elif ok and ssl_ok:
                    if not egress and ssl_egress:
                        egress = ssl_egress
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
