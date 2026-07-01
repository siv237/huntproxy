"""Proxy handlers — proxy/socks5/transparent runner control, selection, detail views."""

import asyncio
import json
from urllib.parse import unquote

from hunt.geo import country_code_from_name, country_flag, country_name_from_code
from hunt.handlers import _qs


class ProxyHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _handle_proxy_status(self, raw_path, body):
        return json.dumps(self.server.proxy.get_status()), 200, "application/json"

    async def _handle_proxy_alive(self, raw_path, body):
        # IP-blacklisted proxies are no longer a hard sentence: they can be
        # selected as upstream but with a reduced score. Only operator-curated
        # manual blacklists are excluded here.
        ratings = [r for r in self.state.ratings.values()
                   if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
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
        port = int(qs.get("port", 17277))
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
        port = int(qs.get("port", 17278))
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
        port = int(qs.get("port", 17477))
        self.state._transparent_port = port
        self.state._save_state()
        self.state._log_action("transparent.start", str(port))
        await self.server.transparent.start(port)
        return json.dumps(self.server.transparent.get_status()), 200, "application/json"

    async def _handle_transparent_stop(self, raw_path, body):
        self.state._log_action("transparent.stop")
        await self.server.transparent.stop()
        return json.dumps({"ok": True}), 200, "application/json"

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
                 if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
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
        if address:
            host, port_str = address.rsplit(":", 1)
            port = int(port_str)
            is_socks = port in (1080, 10808, 9050, 4145)
            http_task = asyncio.create_task(self.state._check_proxy(address))
            ssl_task = asyncio.create_task(self.state._check_ssl(address))
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
            speed = 0.0
            if ok:
                use_ssl = ssl_ok and not is_socks
                try:
                    speed = await self.state._measure_speed(host, port, is_socks, use_ssl=use_ssl, supports_connect=supports_connect)
                except Exception:
                    speed = 0.0
            self.state._update_rating(address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
            self.state._save_state()
            self.state._save_working_file()
            return json.dumps({"ok": ok, "address": address}), 200, "application/json"
        return json.dumps({"ok": False, "error": "no address"}), 400, "application/json"

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

    async def _handle_proxy_detail(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        addr = path[len("/api/proxy/"):]
        addr = unquote(addr)
        r = self.state.ratings.get(addr)
        if r:
            d = r.to_dict()
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
        limit = int(qs.get("limit", 30))
        data = self.state.get_proxy_checks(addr, limit)
        return json.dumps(data), 200, "application/json"

    async def _handle_proxy_heatmap(self, raw_path, body):
        qs = _qs(raw_path)
        hours = int(qs.get("hours", 72))
        data = self.state.get_proxy_heatmap(hours)
        return json.dumps(data), 200, "application/json"

    async def _handle_proxies(self, raw_path, body):
        qs = _qs(raw_path)
        status = qs.get("status", "")
        page = int(qs.get("page", 1))
        limit = int(qs.get("limit", 20))
        mode = qs.get("mode", "")
        all_proxies = list(self.state.ratings.values())
        if mode == "grouped":
            sources_map = {}
            for s in self.state.get_proxy_sources():
                sources_map[s["id"]] = s.get("name", s["id"])
            groups = {}
            if qs.get("group_by") == "source":
                for r in all_proxies:
                    src_ids = self.state._addr_sources.get(r.address, [])
                    if not src_ids:
                        key = "_unknown"
                        label = "Unknown source"
                    else:
                        key = src_ids[0]
                        label = sources_map.get(key, key)
                    if key not in groups:
                        groups[key] = {"key": key, "label": label, "total": 0, "alive": 0, "dead": 0}
                    groups[key]["total"] += 1
                    if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist:
                        groups[key]["alive"] += 1
                    else:
                        groups[key]["dead"] += 1
            elif qs.get("group_by") == "protocol":
                for r in all_proxies:
                    proto = r.protocol or "http"
                    if proto in ("socks5", "socks4"):
                        key = proto
                    elif proto == "https" or r.ssl_supported:
                        key = "https"
                    else:
                        key = "http"
                    labels = {"http": "HTTP", "https": "HTTPS", "socks4": "SOCKS4", "socks5": "SOCKS5"}
                    if key not in groups:
                        groups[key] = {"key": key, "label": labels.get(key, key.upper()), "total": 0, "alive": 0, "dead": 0}
                    groups[key]["total"] += 1
                    if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist:
                        groups[key]["alive"] += 1
                    else:
                        groups[key]["dead"] += 1
            else:
                for r in all_proxies:
                    cc = r.country_code or country_code_from_name(r.country) or "??"
                    if cc not in groups:
                        groups[cc] = {"key": cc, "label": f"{country_flag(cc)} {country_name_from_code(cc)}", "total": 0, "alive": 0, "dead": 0}
                    groups[cc]["total"] += 1
                    if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist:
                        groups[cc]["alive"] += 1
                    else:
                        groups[cc]["dead"] += 1
            result = []
            for g in groups.values():
                g["alive_pct"] = round(g["alive"] / g["total"] * 100, 1) if g["total"] else 0
                if status == "alive" and g["alive"] == 0:
                    continue
                elif status == "dead" and g["dead"] == 0:
                    continue
                result.append(g)
            result.sort(key=lambda g: g["alive"], reverse=True)
            return json.dumps({"groups": result, "total": len(all_proxies)}), 200, "application/json"
        if mode == "group-proxies":
            group_key = qs.get("group_key", "")
            group_by = qs.get("group_by", "country")
            group_status = qs.get("status", "")
            all_ratings = list(self.state.ratings.values())
            sources_map = {}
            for s in self.state.get_proxy_sources():
                sources_map[s["id"]] = s.get("name", s["id"])
            if group_by == "source":
                filtered = [r for r in all_ratings if (
                    (self.state._addr_sources.get(r.address, []) or ["_unknown"])[0] == group_key
                )]
            elif group_by == "protocol":
                def _proto_key(r):
                    proto = r.protocol or "http"
                    if proto in ("socks5", "socks4"):
                        return proto
                    if proto == "https" or r.ssl_supported:
                        return "https"
                    return "http"
                filtered = [r for r in all_ratings if _proto_key(r) == group_key]
            else:
                filtered = [r for r in all_ratings if (r.country_code or country_code_from_name(r.country) or "??") == group_key]
            if group_status == "alive":
                filtered = [r for r in filtered if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
            elif group_status == "dead":
                filtered = [r for r in filtered if r.last_status == "failed"]
            elif group_status == "blacklisted":
                filtered = [r for r in filtered if r.is_blacklisted]
            filtered.sort(key=lambda r: r.score, reverse=True)
            return json.dumps({"proxies": [r.to_dict() for r in filtered]}), 200, "application/json"
        filtered_proxies = all_proxies
        if status == "alive":
            filtered_proxies = [r for r in filtered_proxies if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
        elif status == "dead":
            filtered_proxies = [r for r in filtered_proxies if r.last_status == "failed"]
        elif status == "blacklisted":
            filtered_proxies = [r for r in filtered_proxies if r.is_blacklisted]
        total = len(filtered_proxies)
        start = (page - 1) * limit
        end = start + limit
        page_data = filtered_proxies[start:end]
        proxy_list = []
        for r in page_data:
            d = r.to_dict()
            d["source_ids"] = self.state._addr_sources.get(r.address, [])
            proxy_list.append(d)
        return json.dumps({
            "total": total,
            "page": page,
            "limit": limit,
            "proxies": proxy_list,
        }), 200, "application/json"
