"""Proxy handlers — proxy/socks5/transparent runner control, selection, detail views."""

import asyncio
import json
import logging
import time
from urllib.parse import unquote

from hunt.handlers import _qs, _int_param
from hunt.handlers.proxy_groups import ProxyGroupMixin

logger = logging.getLogger(__name__)

class ProxyHandlers(ProxyGroupMixin):
    STATUS_TTL = 2.0

    def __init__(self, state, server=None):
        self.state = state
        self.server = server
        self._status_lock = asyncio.Lock()
        self._status_cache_ts = 0.0
        self._status_cache_data = None

    async def _handle_proxy_status(self, raw_path, body):
        # get_status enriches switch history with a traffic_log aggregation
        # that can take seconds on a large DB. The UI polls this endpoint
        # every couple of seconds; without coalescing, overlapping polls
        # stack heavy thread-pool jobs until the executor saturates and the
        # whole UI hangs. TTL cache + single-flight: at most one computation
        # per TTL window, everyone else shares its result.
        cached = self._status_cache_data
        if cached is not None and time.monotonic() - self._status_cache_ts < self.STATUS_TTL:
            return json.dumps(cached), 200, "application/json"
        async with self._status_lock:
            if self._status_cache_data is not None and \
                    time.monotonic() - self._status_cache_ts < self.STATUS_TTL:
                return json.dumps(self._status_cache_data), 200, "application/json"
            status = await asyncio.to_thread(self.server.proxy.get_status)
            self._status_cache_data = status
            self._status_cache_ts = time.monotonic()
        return json.dumps(status), 200, "application/json"

    async def _handle_proxy_ping(self, raw_path, body):
        return json.dumps(self.state.get_proxy_ping_status()), 200, "application/json"

    async def _handle_proxy_alive(self, raw_path, body):
        # IP-blacklisted proxies are no longer a hard sentence: they can be
        # selected as upstream but with a reduced score. Only operator-curated
        # manual blacklists are excluded here.
        ratings = [r for r in self.state.ratings.values()
                   if r.pool_eligible]
        ratings.sort(key=lambda r: r.score, reverse=True)
        ip_bl_total = len(self.state.get_ip_blacklist_sources())
        result = []
        for r in ratings:
            d = r.to_pool_dict()
            d["ip_blacklist_sources_total"] = ip_bl_total
            result.append(d)
        return json.dumps(result), 200, "application/json"

    async def _handle_proxy_start(self, raw_path, body):
        qs = _qs(raw_path)
        port = _int_param(qs, "port", 17277)
        self.state._log_action("proxy.start", str(port))
        await self.server.proxy.start(port)
        return json.dumps(self.server.proxy.get_status()), 200, "application/json"

    async def _handle_proxy_stop(self, raw_path, body):
        self.state._log_action("proxy.stop")
        await self.server.proxy.stop()
        self.state._save_state()
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_socks5_status(self, raw_path, body):
        return json.dumps(self.server.socks5.get_status()), 200, "application/json"

    async def _handle_socks5_start(self, raw_path, body):
        qs = _qs(raw_path)
        port = _int_param(qs, "port", 17278)
        self.state._socks5_port = port
        self.state._save_state()
        self.state._log_action("socks5.start", str(port))
        await self.server.socks5.start(port)
        return json.dumps(self.server.socks5.get_status()), 200, "application/json"

    async def _handle_socks5_stop(self, raw_path, body):
        self.state._log_action("socks5.stop")
        await self.server.socks5.stop()
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_transparent_status(self, raw_path, body):
        return json.dumps(self.server.transparent.get_status()), 200, "application/json"

    async def _handle_transparent_start(self, raw_path, body):
        qs = _qs(raw_path)
        port = _int_param(qs, "port", 17477)
        self.state._transparent_port = port
        self.state._save_state()
        self.state._log_action("transparent.start", str(port))
        await self.server.transparent.start(port)
        return json.dumps(self.server.transparent.get_status()), 200, "application/json"

    async def _handle_transparent_stop(self, raw_path, body):
        self.state._log_action("transparent.stop")
        await self.server.transparent.stop()
        # The listener is gone, so any redirect rules now point at a dead port
        # and would black-hole traffic. Drop ALL interception rules (both
        # whole-machine and selective) and clear the selective master flag.
        try:
            import hunt.interception_reconcile as rec
            import hunt.interception_selective as ise
            ok, _ = await rec.run_setup_iptables(["stop"])
            if ise.get_config(self.state).get("selective_enabled"):
                ise.set_config(self.state, {"selective_enabled": False})
            if not ok:
                self.state._emit("Transparent stopped; interception rules may remain (no root)", "warn")
        except Exception:
            logger.debug("interception cleanup on transparent stop failed", exc_info=True)
        return json.dumps({"ok": True}), 200, "application/json"

    # ── Interception (whole-machine transparent redirect) ────────────────

    async def _handle_proxy_select(self, raw_path, body):
        qs = _qs(raw_path)
        address = qs.get("address") or None
        self.server.proxy.select(address)
        self.state._proxy_active_addr = self.server.proxy.active_proxy_addr
        self.state._proxy_direct_mode = self.server.proxy.direct_mode
        self.state._save_state()
        self.state._log_action("proxy.select", address or "none")
        return json.dumps({"ok": True, "address": address}), 200, "application/json"

    async def _handle_proxy_next(self, raw_path, body):
        alive = [r for r in self.state.ratings.values()
                 if r.pool_eligible]
        alive.sort(key=lambda r: r.score, reverse=True)
        current = self.server.proxy.active_proxy_addr
        next_proxy = None
        for r in alive:
            if r.address != current:
                next_proxy = r
                break
        if next_proxy:
            self.server.proxy.select(next_proxy.address)
            self.state._proxy_active_addr = self.server.proxy.active_proxy_addr
            self.state._save_state()
            self.state._log_action("proxy.next", next_proxy.address)
            return json.dumps({"ok": True, "address": next_proxy.address}), 200, "application/json"
        self.state._log_action("proxy.next", "no-other")
        return json.dumps({"ok": False, "error": "no other alive proxy"}), 200, "application/json"

    async def _handle_proxy_recheck(self, raw_path, body):
        qs = _qs(raw_path)
        address = qs.get("address", "").strip()
        self.state._log_action("proxy.recheck", address or "no-addr")
        if not address:
            return json.dumps({"ok": False, "error": "no address"}), 400, "application/json"
        host, port_str = address.rsplit(":", 1)
        port = int(port_str)
        is_socks = port in (1080, 10808, 9050, 4145)
        results = await asyncio.gather(
            asyncio.create_task(self.state._check_proxy(address)),
            asyncio.create_task(self.state._check_ssl(address)),
            return_exceptions=True,
        )
        merged = self.state._merge_check_results(list(results) + [{}], address)
        ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, ssl_ok, _, _ = (
            merged["ok"], merged["country"], merged["supports_connect"],
            merged["mitm_suspect"], merged["egress"], merged["listen"],
            merged["http_latency"], merged["cc"], merged["ssl_ok"],
            merged["ssl_egress"], merged["ssl_supports_connect"],
        )
        speed = 0.0
        if ok:
            use_ssl = ssl_ok and not is_socks
            try:
                speed = await self.state._measure_speed(host, port, is_socks, use_ssl=use_ssl, supports_connect=supports_connect)
            except Exception:
                speed = 0.0
        self.state._update_rating(address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok,
                                  fraud=merged.get("fraud") or {})
        self.state._save_state()
        self.state._save_working_file()
        return json.dumps({"ok": ok, "address": address}), 200, "application/json"

    async def _handle_proxy_direct(self, raw_path, body):
        qs = _qs(raw_path)
        en = qs.get("on", "true").lower() != "false"
        self.server.proxy.direct_mode = en
        if en:
            self.server.proxy.active_proxy_addr = None
        self.state._proxy_direct_mode = en
        self.state._proxy_active_addr = self.server.proxy.active_proxy_addr
        self.server.proxy._record_switch("direct" if en else "proxy", None)
        self.state._emit(f"Direct mode: {'ON' if en else 'OFF'}", "info")
        self.state._save_state()
        return json.dumps({"ok": True, "direct_mode": en}), 200, "application/json"

    async def _handle_proxy_fraud(self, raw_path, body):
        """Принудительная fraud-проверка одного прокси (без ожидания health-цикла).
        Ходит через сам прокси (ip-api + риск-скор proxycheck.io). Свежий
        результат (<10 мин) — из кэша; ?force=1 выполняет реальную перепроверку.
        """
        qs = _qs(raw_path)
        addr = qs.get("addr", "")
        force = qs.get("force") in ("1", "true")
        if not addr:
            return json.dumps({"ok": False, "error": "no addr"}), 400, "application/json"
        r = self.state.ratings.get(addr)
        if r is None:
            return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
        now = time.time()
        if not force and r.fraud_checked_ts and now - r.fraud_checked_ts < 600:
            return json.dumps(self._fraud_response(r, cached=True)), 200, "application/json"
        try:
            results = await asyncio.gather(
                asyncio.create_task(self.state._check_proxy(addr)),
                asyncio.create_task(self.state._check_ssl(addr)),
                asyncio.create_task(self.state._fetch_fraud_score(addr, r.egress_ip)),
                return_exceptions=True,
            )
            merged = self.state._merge_check_results(results, addr)
            ok = bool(merged.get("ok"))
            egress = merged.get("egress") or {}
            fraud = merged.get("fraud") or {}
        except Exception as exc:
            logger.warning("fraud check %s: %s", addr, str(exc)[:200])
            ok, egress, fraud = False, {}, {}
        if "egress_hosting" not in egress:
            logger.warning("fraud check %s: egress без fraud-данных (ok=%s)", addr, ok)
        if "egress_hosting" in egress:
            r.fraud_hosting = bool(egress.get("egress_hosting"))
            r.fraud_proxy = bool(egress.get("egress_proxy"))
            r.fraud_mobile = bool(egress.get("egress_mobile"))
            touched = True
        else:
            touched = False
        score = fraud.get("score")
        if isinstance(score, int) and 0 <= score <= 100:
            self.state._apply_fraud(r, fraud)
            touched = True
        if touched:
            r.fraud_checked_ts = now
            self.state._dirty_ratings.add(addr)
            self.state._save_dirty_ratings()
            return json.dumps(self._fraud_response(r, cached=False)), 200, "application/json"
        r.fraud_attempt_ts = now
        self.state._dirty_ratings.add(addr)
        self.state._save_dirty_ratings()
        return json.dumps({"ok": False, "error": "check failed",
                           "fraud_score": r.fraud_score, "fraud_verdict": r.fraud_verdict}), 200, "application/json"

    @staticmethod
    def _fraud_response(r, cached: bool) -> dict:
        return {"ok": True, "cached": cached,
                "fraud_score": r.fraud_score, "fraud_score_raw": r.fraud_score_raw,
                "fraud_verdict": r.fraud_verdict,
                "fraud_hosting": r.fraud_hosting, "fraud_proxy": r.fraud_proxy,
                "fraud_mobile": r.fraud_mobile,
                "fraud_checked_ts": r.fraud_checked_ts}

    async def _handle_proxy_detail(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        addr = path[len("/api/proxy/"):]
        addr = unquote(addr)
        r = self.state.ratings.get(addr)
        if r:
            d = r.to_dict()
            d["score_breakdown"] = r.score_breakdown()
            d["source_ids"] = self.state._addr_sources.get(r.address, [])
            total_sources = len(self.state.get_proxy_sources())
            d["sources_total"] = total_sources
            d["ip_blacklist_sources_total"] = len(self.state.get_ip_blacklist_sources())
            return json.dumps(d), 200, "application/json"
        return json.dumps({"error": "not found"}), 404, "application/json"

    async def _handle_proxy_checks(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        addr = path[len("/api/proxy-checks/"):]
        addr = unquote(addr)
        qs = _qs(raw_path)
        limit = _int_param(qs, "limit", 30)
        data = self.state.get_proxy_checks(addr, limit)
        return json.dumps(data), 200, "application/json"

    async def _handle_proxy_heatmap(self, raw_path, body):
        qs = _qs(raw_path)
        hours = _int_param(qs, "hours", 72)
        data = self.state.get_proxy_heatmap(hours)
        return json.dumps(data), 200, "application/json"

    async def _handle_proxies(self, raw_path, body):
        qs = _qs(raw_path)
        mode = qs.get("mode", "")
        if mode == "grouped":
            return await self._proxies_grouped(qs)
        if mode == "group-proxies":
            return await self._proxies_group_proxies(qs)
        return await self._proxies_list(qs)

    def _proxy_alive(self, r):
        return r.pool_eligible
