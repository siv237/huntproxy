"""Per-check helpers for the validation pipeline, extracted from check_validation.py."""

import time


class CheckValidationHelpersMixin:
    async def _handle_blacklisted(self, addr, lock, counted) -> bool:
        async with lock:
            if getattr(self, '_health_running', False):
                return True
            if not counted:
                self.checked += 1
        return True

    async def _should_retry_after_result(self) -> bool:
        if self._internet_suspect:
            await self._pause_event.wait()
            return True
        if self._check_streak >= 10 and self._fail_streak / self._check_streak > 0.7:
            await self._auto_pause_if_internet_down()
        return False

    async def _measure_check_speed(self, addr, ok, wid, _proto, country, cc, ssl_ok, supports_connect) -> float:
        self._active_checks[wid] = {"addr": addr, "step": "speed_wait", "started": time.time(), "protocol": _proto, "country": country, "cc": cc}
        host, port_str = addr.rsplit(":", 1)
        is_socks = port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145)
        use_ssl = ssl_ok and not is_socks
        def _on_active():
            self._active_checks[wid] = {"addr": addr, "step": "speed", "started": time.time(), "protocol": _proto, "country": country, "cc": cc}
        try:
            return await self._measure_speed(host, int(port_str), is_socks,
                                              use_ssl=use_ssl, supports_connect=supports_connect,
                                              on_active=_on_active)
        except Exception:
            return 0.0

    async def _handle_fast_fail(self, addr, lock, ctx, counted) -> bool:
        """Handle fast-fail case. Returns True if caller should return."""
        need_auto_pause = False
        async with lock:
            if getattr(self, '_health_running', False):
                return True
            self._fail_streak += 1
            self._check_streak += 1
            if not counted:
                self.checked += 1
            ctx.fail_count += 1
            self.failed = ctx.fail_count
            if self._check_streak >= 3 and self._fail_streak / self._check_streak > 0.7:
                need_auto_pause = True
        if need_auto_pause:
            await self._auto_pause_if_internet_down()
        return False

    async def _record_check_result(self, addr, ok, country, http_latency, supports_connect,
                                    mitm_suspect, egress, listen, speed, cc, ssl_ok,
                                    lock, ctx, counted, fraud=None) -> bool:
        """Record check result under lock. Returns True if caller should return."""
        async with lock:
            if getattr(self, '_health_running', False):
                return True
            if self._internet_suspect:
                return False
            if not counted:
                self.checked += 1
            self._check_streak += 1
            if ok:
                ctx.ok_count += 1
                self.working = ctx.ok_count
                existing = self.ratings.get(addr)
                if existing is not None and existing.checks_ok > 0:
                    ctx.confirmed_count += 1
                    self.confirmed_working = ctx.confirmed_count
                else:
                    ctx.new_count += 1
                    self.new_working = ctx.new_count
                self.last_proxy = addr
                self.last_country = country
                self._fail_streak = 0
            else:
                ctx.fail_count += 1
                self.failed = ctx.fail_count
                self._fail_streak += 1
            self._update_rating(addr, ok, country, http_latency, supports_connect,
                                mitm_suspect, egress, listen, speed, country_code=cc,
                                ssl_supported=ssl_ok, fraud=fraud)
            if self.checked % 25 == 0 or ok:
                pct = int(100 * self.checked / max(1, self.checking_total))
                self._emit(
                    f"{pct}% {self.checked}/{self.checking_total} | "
                    f"working: {ctx.ok_count} | last: {addr} {country}",
                    "progress"
                )
        return False
