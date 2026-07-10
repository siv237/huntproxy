"""Proxy handlers — proxy/socks5/transparent runner control, selection, detail views."""

import asyncio
import fcntl
import json
import logging
import os
import socket
import struct
from urllib.parse import unquote

from hunt.constants import DATA_DIR
from hunt.geo import country_code_from_name, country_flag, country_name_from_code
from hunt.handlers import _qs, _int_param

logger = logging.getLogger(__name__)

# State file written by setup_iptables.sh after start/stop (read by the web
# backend so it can show interception status without any root privileges).
INTERCEPTION_STATE_FILE = DATA_DIR / "transparent_state.json"


def _detect_local_ips():
    """Enumerate non-loopback IPv4 addresses without root (ioctl SIOCGIFADDR)."""
    SIOCGIFADDR = 0x8915
    ips = []
    try:
        with open("/proc/net/dev") as f:
            ifaces = [ln.split(":", 1)[0].strip() for ln in f.readlines()[2:] if ":" in ln]
    except Exception:
        logger.debug("suppressed", exc_info=True)
        ifaces = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for iface in ifaces:
            try:
                ifr = iface.encode() + b"\x00" * 24
                res = fcntl.ioctl(s.fileno(), SIOCGIFADDR, ifr)
                ip = socket.inet_ntoa(res[20:24])
                if ip != "127.0.0.1":
                    ips.append(ip)
            except Exception:
                logger.debug("suppressed", exc_info=True)
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return sorted(set(ips))


def _read_interception_state():
    try:
        if INTERCEPTION_STATE_FILE.exists():
            data = json.loads(INTERCEPTION_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return {"active": False}


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
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_interception(self, raw_path, body):
        """Whole-machine transparent interception status + admin command.

        The web backend has no root, so it only *generates* the command an
        admin pastes into a root terminal and reads back the on/off state from
        the file ``setup_iptables.sh`` writes (no iptables read privilege).

        Loop prevention excludes the proxy's own upstream connections by
        **cgroup v2** (``-m cgroup --path``) — the modern replacement for the
        removed ``--pid-owner``. The command moves this server process into a
        dedicated cgroup (``huntproxy``) and redirects all other machine
        traffic to the proxy. This isolates only the proxy's traffic even when
        it shares the operator's UID, so user apps are still intercepted.
        Local/reserved destinations are returned by the script itself, so no
        ``--own-ip`` is needed.
        """
        own_ips = _detect_local_ips()
        uid = os.getuid()
        pid = os.getpid()
        redirect_port = getattr(self.server.transparent, "port", None) or \
            getattr(self.state, "_transparent_port", None) or 17477
        apply_cmd = (
            f"sudo ./setup_iptables.sh start --redirect-port {redirect_port} "
            f"--exclude-cgroup huntproxy --cgroup-pid {pid}"
        )
        revert_cmd = "sudo ./setup_iptables.sh stop"
        return json.dumps({
            "own_ips": own_ips,
            "proxy_pid": pid,
            "proxy_uid": uid,
            "apply_command": apply_cmd,
            "revert_command": revert_cmd,
            "status": _read_interception_state(),
        }), 200, "application/json"

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
        merged = self.state._merge_check_results(results, address)
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
        self.state._update_rating(address, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
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
        return (r.last_status == "ok" or r.in_grace) and not r.in_blacklist

    async def _proxies_grouped(self, qs):
        all_proxies = list(self.state.ratings.values())
        status = qs.get("status", "")
        sources_map = {s["id"]: s.get("name", s["id"]) for s in self.state.get_proxy_sources()}
        group_by = qs.get("group_by", "country")
        if group_by == "source":
            groups = self._group_by_source(all_proxies, sources_map)
        elif group_by == "protocol":
            groups = self._group_by_protocol(all_proxies)
        else:
            groups = self._group_by_country(all_proxies)
        result = []
        for g in groups.values():
            g["alive_pct"] = round(g["alive"] / g["total"] * 100, 1) if g["total"] else 0
            if status == "alive" and g["alive"] == 0:
                continue
            if status == "dead" and g["dead"] == 0:
                continue
            result.append(g)
        result.sort(key=lambda g: g["alive"], reverse=True)
        return json.dumps({"groups": result, "total": len(all_proxies)}), 200, "application/json"

    def _group_by_source(self, proxies, sources_map):
        groups = {}
        for r in proxies:
            src_ids = self.state._addr_sources.get(r.address, [])
            if not src_ids:
                key, label = "_unknown", "Unknown source"
            else:
                key, label = src_ids[0], sources_map.get(src_ids[0], src_ids[0])
            self._add_to_group(groups, key, label, r)
        return groups

    def _group_by_protocol(self, proxies):
        groups = {}
        labels = {"http": "HTTP", "https": "HTTPS", "socks4": "SOCKS4", "socks5": "SOCKS5"}
        for r in proxies:
            proto = r.protocol or "http"
            if proto in ("socks5", "socks4"):
                key = proto
            elif proto == "https" or r.ssl_supported:
                key = "https"
            else:
                key = "http"
            self._add_to_group(groups, key, labels.get(key, key.upper()), r)
        return groups

    def _group_by_country(self, proxies):
        groups = {}
        for r in proxies:
            cc = r.country_code or country_code_from_name(r.country) or "??"
            label = f"{country_flag(cc)} {country_name_from_code(cc)}"
            self._add_to_group(groups, cc, label, r)
        return groups

    def _add_to_group(self, groups, key, label, r):
        if key not in groups:
            groups[key] = {"key": key, "label": label, "total": 0, "alive": 0, "dead": 0}
        groups[key]["total"] += 1
        if self._proxy_alive(r):
            groups[key]["alive"] += 1
        else:
            groups[key]["dead"] += 1

    async def _proxies_group_proxies(self, qs):
        group_key = qs.get("group_key", "")
        group_by = qs.get("group_by", "country")
        group_status = qs.get("status", "")
        all_ratings = list(self.state.ratings.values())
        if group_by == "source":
            filtered = [r for r in all_ratings if (
                (self.state._addr_sources.get(r.address, []) or ["_unknown"])[0] == group_key
            )]
        elif group_by == "protocol":
            filtered = [r for r in all_ratings if self._proto_key(r) == group_key]
        else:
            filtered = [r for r in all_ratings if (r.country_code or country_code_from_name(r.country) or "??") == group_key]
        filtered = self._filter_by_status(filtered, group_status)
        filtered.sort(key=lambda r: r.score, reverse=True)
        return json.dumps({"proxies": [r.to_dict() for r in filtered]}), 200, "application/json"

    def _proto_key(self, r):
        proto = r.protocol or "http"
        if proto in ("socks5", "socks4"):
            return proto
        if proto == "https" or r.ssl_supported:
            return "https"
        return "http"

    def _filter_by_status(self, proxies, status):
        if status == "alive":
            return [r for r in proxies if self._proxy_alive(r)]
        if status == "dead":
            return [r for r in proxies if r.last_status == "failed"]
        if status == "blacklisted":
            return [r for r in proxies if r.is_blacklisted]
        return proxies

    async def _proxies_list(self, qs):
        status = qs.get("status", "")
        page = _int_param(qs, "page", 1)
        limit = _int_param(qs, "limit", 20)
        all_proxies = list(self.state.ratings.values())
        filtered = self._filter_by_status(all_proxies, status)
        total = len(filtered)
        start = (page - 1) * limit
        page_data = filtered[start:start + limit]
        proxy_list = []
        for r in page_data:
            d = r.to_dict()
            d["source_ids"] = self.state._addr_sources.get(r.address, [])
            proxy_list.append(d)
        return json.dumps({
            "total": total, "page": page, "limit": limit, "proxies": proxy_list,
        }), 200, "application/json"
