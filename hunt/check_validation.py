"""Functional split of the huntproxy backend."""

import asyncio
import time
from hunt.constants import logger


class _ValidationContext:
    """Shared state for a single _validate_all run.

    Replaces the nonlocal-closure pattern so check_one can be a method
    instead of a nested function (which inflates cyclomatic complexity).
    """
    def __init__(self):
        self.ok_count = 0
        self.fail_count = 0
        self.new_count = 0
        self.confirmed_count = 0
        self.ctr = 0


class CheckValidationMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})

    def _detect_protocol(self, addr: str) -> str:
        try:
            p = int(addr.rsplit(":", 1)[1])
            if p in (1080, 10808, 9050):
                return "socks5"
            if p == 4145:
                return "socks4"
        except Exception:
            logger.debug("suppressed", exc_info=True)
        return "http"

    def _merge_check_results(self, results, addr: str) -> dict:
        http_r = results[0]
        ssl_r = results[1]
        if isinstance(http_r, Exception):
            ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = False, "", False, False, {}, {}, 0.0, "", False
        else:
            ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = http_r
        if isinstance(ssl_r, Exception):
            ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = False, "", "", {}, 0.0, False
        else:
            ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = ssl_r
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
        if ok and not self._is_socks_addr(addr) and not supports_connect:
            ok = False
        return {
            "ok": ok, "country": country, "supports_connect": supports_connect,
            "mitm_suspect": mitm_suspect, "egress": egress, "listen": listen,
            "http_latency": http_latency, "cc": cc, "fast_fail": fast_fail,
            "ssl_ok": ssl_ok, "ssl_egress": ssl_egress,
            "ssl_supports_connect": ssl_supports_connect,
        }

    async def _validate_all(self, proxies: set):
        sem = asyncio.Semaphore(self.parallel)
        lock = asyncio.Lock()
        ctx = _ValidationContext()
        self._fail_streak = 0
        self._check_streak = 0

        tasks = [asyncio.create_task(self._check_one(addr, sem, lock, ctx)) for p in proxies for addr in [p]]
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
                logger.debug("suppressed", exc_info=True)
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

    async def _check_one(self, addr: str, sem: asyncio.Semaphore, lock: asyncio.Lock, ctx: _ValidationContext):
        wid = ctx.ctr; ctx.ctr += 1
        counted = False
        _proto = self._detect_protocol(addr)
        self._active_checks[wid] = {"addr": addr, "step": "queued", "started": time.time(), "protocol": _proto}
        try:
            while True:
                if self._paused:
                    await self._pause_event.wait()
                if addr in self.blacklist:
                    if await self._handle_blacklisted(addr, lock, counted):
                        return
                self._active_checks[wid] = {"addr": addr, "step": "queued", "started": time.time(), "protocol": _proto}
                async with sem:
                    if self._internet_suspect:
                        await self._pause_event.wait()
                        continue
                    self._active_checks[wid] = {"addr": addr, "step": "connect", "started": time.time(), "protocol": _proto}
                    results = await asyncio.gather(
                        asyncio.create_task(self._check_proxy(addr)),
                        asyncio.create_task(self._check_ssl(addr)),
                        return_exceptions=True,
                    )
                    merged = self._merge_check_results(results, addr)
                    if merged["fast_fail"] and not merged["ok"] and not merged["ssl_ok"]:
                        if await self._handle_fast_fail(addr, lock, ctx, counted):
                            return
                        if self._internet_suspect:
                            await self._pause_event.wait()
                            continue
                        return
                    ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, ssl_ok, _, _ = (
                        merged["ok"], merged["country"], merged["supports_connect"],
                        merged["mitm_suspect"], merged["egress"], merged["listen"],
                        merged["http_latency"], merged["cc"], merged["ssl_ok"],
                        merged["ssl_egress"], merged["ssl_supports_connect"],
                    )
                    speed = await self._measure_check_speed(addr, ok, wid, _proto, country, cc, ssl_ok, supports_connect) if ok else 0.0
                    if await self._record_check_result(addr, ok, country, http_latency, supports_connect,
                                                        mitm_suspect, egress, listen, speed, cc, ssl_ok,
                                                        lock, ctx, counted):
                        return
                    counted = True
                    if await self._should_retry_after_result():
                        continue
                    return
        finally:
            self._active_checks.pop(wid, None)

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
        self._active_checks[wid] = {"addr": addr, "step": "speed", "started": time.time(), "protocol": _proto, "country": country, "cc": cc}
        host, port_str = addr.rsplit(":", 1)
        is_socks = port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145)
        use_ssl = ssl_ok and not is_socks
        try:
            return await self._measure_speed(host, int(port_str), is_socks,
                                              use_ssl=use_ssl, supports_connect=supports_connect)
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
                                    lock, ctx, counted) -> bool:
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
                                mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
            if self.checked % 25 == 0 or ok:
                pct = int(100 * self.checked / max(1, self.checking_total))
                self._emit(
                    f"{pct}% {self.checked}/{self.checking_total} | "
                    f"working: {ctx.ok_count} | last: {addr} {country}",
                    "progress"
                )
        return False
