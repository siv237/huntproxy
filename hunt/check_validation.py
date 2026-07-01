"""Functional split of the huntproxy backend."""

import asyncio
import json
import ssl as _ssl
import time
from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating

class CheckValidationMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    async def _validate_all(self, proxies: set):
            sem = asyncio.Semaphore(self.parallel)
            lock = asyncio.Lock()
            ok_count = 0
            fail_count = 0
            new_count = 0
            confirmed_count = 0
            self._fail_streak = 0
            self._check_streak = 0
            _ctr = [0]

            async def check_one(addr: str):
                nonlocal ok_count, fail_count, new_count, confirmed_count
                wid = _ctr[0]; _ctr[0] += 1
                counted = False
                try:
                    _p = int(addr.rsplit(":", 1)[1])
                    _proto = "socks5" if _p in (1080, 10808, 9050) else "socks4" if _p == 4145 else "http"
                except Exception:
                    _proto = "http"
                self._active_checks[wid] = {"addr": addr, "step": "queued", "started": time.time(), "protocol": _proto}
                try:
                    while True:
                        if self._paused:
                            await self._pause_event.wait()
                        if addr in self.blacklist:
                            async with lock:
                                if getattr(self, '_health_running', False):
                                    return
                                if not counted:
                                    self.checked += 1
                                    counted = True
                            return
                        self._active_checks[wid] = {"addr": addr, "step": "queued", "started": time.time(), "protocol": _proto}
                        async with sem:
                            if self._internet_suspect:
                                await self._pause_event.wait()
                                continue
                            self._active_checks[wid] = {"addr": addr, "step": "connect", "started": time.time(), "protocol": _proto}
                            http_task = asyncio.create_task(self._check_proxy(addr))
                            ssl_task = asyncio.create_task(self._check_ssl(addr))
                            results = await asyncio.gather(http_task, ssl_task, return_exceptions=True)
                            if isinstance(results[0], Exception):
                                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = False, "", False, False, {}, {}, 0.0, "", False
                            else:
                                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = results[0]
                            if isinstance(results[1], Exception):
                                ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = False, "", "", {}, 0.0, False
                            else:
                                ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = results[1]
                            if fast_fail and not ok and not ssl_ok:
                                need_auto_pause = False
                                async with lock:
                                    if getattr(self, '_health_running', False):
                                        return
                                    self._fail_streak += 1
                                    self._check_streak += 1
                                    if not counted:
                                        self.checked += 1
                                        counted = True
                                    fail_count += 1
                                    self.failed = fail_count
                                    if self._check_streak >= 3 and self._fail_streak / self._check_streak > 0.7:
                                        need_auto_pause = True
                                if need_auto_pause:
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
                                supports_connect = ssl_supports_connect
                            elif ok and not ssl_ok:
                                pass
                            elif ok and ssl_ok:
                                if not egress and ssl_egress:
                                    egress = ssl_egress
                                if not supports_connect and ssl_supports_connect:
                                    supports_connect = ssl_supports_connect
                            # Non-SOCKS proxies must support CONNECT to be useful for HTTPS.
                            if ok and not self._is_socks_addr(addr) and not supports_connect:
                                ok = False
                            speed = 0.0
                            if ok:
                                self._active_checks[wid] = {"addr": addr, "step": "speed", "started": time.time(), "protocol": _proto, "country": country, "cc": cc}
                                host, port_str = addr.rsplit(":", 1)
                                is_socks = port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145)
                                use_ssl = ssl_ok and not is_socks
                                try:
                                    speed = await self._measure_speed(host, int(port_str), is_socks,
                                                                       use_ssl=use_ssl, supports_connect=supports_connect)
                                except Exception:
                                    speed = 0.0
                            async with lock:
                                if getattr(self, '_health_running', False):
                                    return
                                if self._internet_suspect:
                                    pass  # handle outside lock
                                else:
                                    if not counted:
                                        self.checked += 1
                                        counted = True
                                    self._check_streak += 1
                                    if ok:
                                        ok_count += 1
                                        self.working = ok_count
                                        existing = self.ratings.get(addr)
                                        if existing is not None and existing.checks_ok > 0:
                                            confirmed_count += 1
                                            self.confirmed_working = confirmed_count
                                        else:
                                            new_count += 1
                                            self.new_working = new_count
                                        self.last_proxy = addr
                                        self.last_country = country
                                        self._fail_streak = 0
                                    else:
                                        fail_count += 1
                                        self.failed = fail_count
                                        self._fail_streak += 1
                                    self._update_rating(addr, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
                                    if self.checked % 25 == 0 or ok:
                                        pct = int(100 * self.checked / max(1, self.checking_total))
                                        self._emit(
                                            f"{pct}% {self.checked}/{self.checking_total} | "
                                            f"working: {ok_count} | last: {addr} {country}",
                                            "progress"
                                        )
                                    if self._check_streak >= 10 and self._fail_streak / self._check_streak > 0.7:
                                        pass  # handle outside lock
                            if self._internet_suspect:
                                await self._pause_event.wait()
                                continue
                            if self._check_streak >= 10 and self._fail_streak / self._check_streak > 0.7:
                                await self._auto_pause_if_internet_down()
                            return
                finally:
                    self._active_checks.pop(wid, None)

            tasks = [asyncio.create_task(check_one(p)) for p in proxies]
            gather_task = asyncio.ensure_future(asyncio.gather(*tasks, return_exceptions=True))
            skip_task = asyncio.ensure_future(self._skip_event.wait())
            overall_timeout = len(proxies) * (self.effective_timeout + 10) // max(1, self.parallel) + 60
            done, pending = await asyncio.wait(
                {gather_task, skip_task}, timeout=overall_timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if skip_task in done and not gather_task.done():
                for t in tasks:
                    if not t.done():
                        t.cancel()
                try:
                    await gather_task
                except Exception:
                    pass
                self._reset_skip()
                self._emit("Validation skipped by user", "warn")
            elif not gather_task.done():
                for t in tasks:
                    if not t.done():
                        t.cancel()
                self._emit("Validation timed out, cancelling stuck tasks", "warn")
            else:
                skip_task.cancel()
            self._save_state()
            self._save_working_file()
            self._rating_updates_since_save = 0
            self._push_history()

