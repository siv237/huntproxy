"""Functional split of the huntproxy backend."""

import asyncio
import json
from typing import Optional

from hunt.constants import STATIC_MIME, WEB_DIR, logger
from hunt.proxy_runner import ProxyRunner
from hunt.socks5_runner import Socks5Runner
from hunt.transparent_runner import TransparentRunner
from hunt.state import HuntState
from hunt.router import Router

# Re-exported for backward compatibility (hunt/__init__.py imports these).
from hunt.handlers import _qs  # noqa: F401
from hunt.web_legacy import WEB_HTML  # noqa: F401

from hunt.handlers.core import CoreHandlers
from hunt.handlers.hunt import HuntHandlers
from hunt.handlers.proxy import ProxyHandlers
from hunt.handlers.pool import PoolHandlers
from hunt.handlers.traffic import TrafficHandlers
from hunt.handlers.sources import SourceHandlers
from hunt.handlers.routing import RoutingHandlers
from hunt.handlers.admin import AdminHandlers


class HuntServer:
    def __init__(self, state: HuntState, host: str, port: int):
        self.state = state
        self.host = host
        self.port = port
        self.proxy = ProxyRunner(state, host)
        self.socks5 = Socks5Runner(state, host)
        self.transparent = TransparentRunner(state, host)
        if hasattr(state, '_socks5_port'):
            self.socks5.port = state._socks5_port
        if hasattr(state, '_transparent_port'):
            self.transparent.port = state._transparent_port
        self._server: Optional[asyncio.AbstractServer] = None
        if hasattr(state, '_proxy_direct_mode'):
            self.proxy.direct_mode = state._proxy_direct_mode
        if hasattr(state, '_proxy_active_addr') and state._proxy_active_addr:
            self.proxy.active_proxy_addr = state._proxy_active_addr
        self._router = Router()
        self._h_core = CoreHandlers(self.state, self)
        self._h_hunt = HuntHandlers(self.state, self)
        self._h_proxy = ProxyHandlers(self.state, self)
        self._h_pool = PoolHandlers(self.state, self)
        self._h_traffic = TrafficHandlers(self.state, self)
        self._h_sources = SourceHandlers(self.state, self)
        self._h_routing = RoutingHandlers(self.state, self)
        self._h_admin = AdminHandlers(self.state, self)
        self._register_routes()

    async def start(self):
        self._server = await asyncio.start_server(
            self._handle, self.host, self.port)
        addr = self._server.sockets[0].getsockname()
        logger.info(f"Hunt web UI: http://{addr[0]}:{addr[1]}/")
        async with self._server:
            await self._server.serve_forever()

    async def stop(self):
        await self.proxy.stop()
        await self.socks5.stop()
        await self.transparent.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=10)
        except Exception:
            writer.close(); return
        if not line:
            writer.close(); return
        try:
            parts = line.split()
            if len(parts) < 2:
                writer.close(); return
            method = parts[0].decode().upper()
            raw_path = parts[1].decode()
            path = raw_path.split("?", 1)[0]
        except Exception:
            writer.close(); return

        headers = {}
        while True:
            try:
                hl = await asyncio.wait_for(reader.readline(), timeout=5)
            except Exception:
                break
            if hl in (b"\r\n", b"\n", b""):
                break
            if b":" in hl:
                k, v = hl.decode(errors="replace").split(":", 1)
                headers[k.strip().lower()] = v.strip()

        cl = int(headers.get("content-length", 0))
        body = b""
        if cl > 0:
            try:
                body = await asyncio.wait_for(reader.readexactly(cl), timeout=10)
            except Exception:
                pass

        response, status, ct = await self._route(method, path, raw_path, body)
        await self._write(writer, status, response, ct)
        try:
            writer.close()
        except Exception:
            pass

    async def _write(self, writer, status, body, ct="application/json", cache_control=None):
        if isinstance(body, str):
            body = body.encode()
        if cache_control is None:
            if ct.startswith("image/") or ct == "image/x-icon" or ct == "application/manifest+json" or ct.startswith("text/css") or ct.startswith("application/javascript"):
                cache_control = "public, max-age=86400"
            else:
                cache_control = "no-store"
        resp = (
            f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: {ct}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Cache-Control: {cache_control}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode() + body
        writer.write(resp)
        try:
            await writer.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, path: str):
        if not WEB_DIR.exists():
            return None
        safe = path.lstrip("/")
        if ".." in safe or safe.startswith("/"):
            return None
        target = WEB_DIR / safe
        try:
            target.resolve().relative_to(WEB_DIR.resolve())
        except ValueError:
            return None
        if not target.exists() or not target.is_file():
            return None
        data = target.read_bytes()
        ext = target.suffix.lower()
        ct = STATIC_MIME.get(ext, "application/octet-stream")
        return data, 200, ct

    async def _route(self, method, path, raw_path, body):
        handler = self._router.match(method, path)
        if handler is not None:
            return await handler(raw_path, body)
        return json.dumps({"error": "not found"}), 404, "application/json"

    def _register_routes(self):
        c, h, p, pl, t, s, r, a = (self._h_core, self._h_hunt, self._h_proxy,
                                   self._h_pool, self._h_traffic, self._h_sources,
                                   self._h_routing, self._h_admin)

        self._router.add_static(["/css/", "/js/", "/img/", "/assets/", "/locales/"], c._handle_static)

        self._router.add("GET", "/legacy", c._handle_legacy)
        self._router.add("GET", "/favicon.ico", c._handle_favicon)
        self._router.add("GET", "/", c._handle_index)
        self._router.add_prefix("GET", "/index", c._handle_index)

        self._router.add("GET", "/api/snapshot", c._handle_snapshot)
        self._router.add_prefix("GET", "/api/events", c._handle_events)

        self._router.add("POST", "/api/hunt/start", h._handle_hunt_start)
        self._router.add("POST", "/api/hunt/stop", h._handle_hunt_stop)
        self._router.add("POST", "/api/hunt/pause", h._handle_hunt_pause)
        self._router.add("POST", "/api/hunt/resume", h._handle_hunt_resume)
        self._router.add("POST", "/api/hunt/skip", h._handle_hunt_skip)

        self._router.add("POST", "/api/blacklist/add", pl._handle_blacklist_add)
        self._router.add("POST", "/api/blacklist/remove", pl._handle_blacklist_remove)
        self._router.add("POST", "/api/favorites/add", pl._handle_favorites_add)
        self._router.add("POST", "/api/favorites/remove", pl._handle_favorites_remove)
        self._router.add("GET", "/api/favorites", pl._handle_favorites_list)

        self._router.add("GET", "/api/proxy/status", p._handle_proxy_status)
        self._router.add("GET", "/api/proxy/alive", p._handle_proxy_alive)
        for m in ("GET", "POST"):
            self._router.add_prefix(m, "/api/proxy/start", p._handle_proxy_start)
            self._router.add(m, "/api/proxy/stop", p._handle_proxy_stop)
            self._router.add_prefix(m, "/api/proxy/select", p._handle_proxy_select)
            self._router.add(m, "/api/proxy/next", p._handle_proxy_next)
            self._router.add_prefix(m, "/api/proxy/recheck", p._handle_proxy_recheck)
            self._router.add_prefix(m, "/api/proxy/direct", p._handle_proxy_direct)
        self._router.add("GET", "/api/socks5/status", p._handle_socks5_status)
        for m in ("GET", "POST"):
            self._router.add_prefix(m, "/api/socks5/start", p._handle_socks5_start)
            self._router.add(m, "/api/socks5/stop", p._handle_socks5_stop)
        self._router.add("GET", "/api/transparent/status", p._handle_transparent_status)
        for m in ("GET", "POST"):
            self._router.add_prefix(m, "/api/transparent/start", p._handle_transparent_start)
            self._router.add(m, "/api/transparent/stop", p._handle_transparent_stop)
        self._router.add_prefix("GET", "/api/proxy/", p._handle_proxy_detail)

        self._router.add("GET", "/api/channel/status", a._handle_channel_status)
        self._router.add("POST", "/api/channel/select", a._handle_channel_select)
        self._router.add_prefix("POST", "/api/settings/country_filter", a._handle_country_filter)

        self._router.add("GET", "/api/countries", c._handle_countries)
        self._router.add_prefix("GET", "/api/system", c._handle_system)
        self._router.add_prefix("GET", "/api/activity", c._handle_activity)
        self._router.add_prefix("GET", "/api/actions", c._handle_actions)
        self._router.add_prefix("GET", "/api/history", c._handle_history)
        self._router.add_prefix("GET", "/api/proxies", p._handle_proxies)
        self._router.add_prefix("GET", "/api/proxy-checks/", p._handle_proxy_checks)
        self._router.add_prefix("GET", "/api/proxy-heatmap", p._handle_proxy_heatmap)
        self._router.add_prefix("GET", "/api/blacklist", pl._handle_blacklist_list)

        self._router.add_prefix("POST", "/api/clear_dead", h._handle_clear_dead)
        self._router.add_prefix("POST", "/api/export", h._handle_export)
        self._router.add_prefix("POST", "/api/import", h._handle_import)
        self._router.add_prefix("POST", "/api/health/start", h._handle_health_start)
        self._router.add_prefix("POST", "/api/health/stop", h._handle_health_stop)

        self._router.add_prefix("GET", "/api/settings", c._handle_settings_get)
        self._router.add_prefix("POST", "/api/settings", c._handle_settings_post)
        self._router.add_prefix("GET", "/api/logs", c._handle_logs)

        self._router.add_prefix("GET", "/api/downloads/count", c._handle_downloads_count)
        self._router.add_prefix("GET", "/api/download/", c._handle_download)

        self._router.add_prefix("GET", "/api/backup/groups", a._handle_backup_groups)
        self._router.add_prefix("POST", "/api/backup", a._handle_backup)
        self._router.add_prefix("POST", "/api/restore", a._handle_restore)

        self._router.add_prefix("GET", "/api/traffic/live", t._handle_traffic_live)
        self._router.add("GET", "/api/traffic", t._handle_traffic)
        self._router.add_prefix("GET", "/api/requests", t._handle_requests)
        self._router.add_prefix("GET", "/api/clients", t._handle_clients)
        self._router.add_prefix("GET", "/api/domains", t._handle_domains)
        self._router.add_prefix("GET", "/api/errors", t._handle_errors)
        self._router.add_prefix("GET", "/api/traffic/routes", t._handle_traffic_routes)
        self._router.add_prefix("GET", "/api/bandwidth", t._handle_bandwidth)
        self._router.add_prefix("GET", "/api/traffic/summary", t._handle_traffic_summary)

        self._router.add("GET", "/api/routing/status", r._handle_routing_status)
        self._router.add("POST", "/api/routing/enable", r._handle_routing_enable)
        self._router.add("POST", "/api/routing/disable", r._handle_routing_disable)
        self._router.add("POST", "/api/routing/default", r._handle_routing_default)
        self._router.add("POST", "/api/routing/reorder", r._handle_routing_reorder)
        self._router.add("POST", "/api/routing/test", r._handle_routing_test)

        self._router.add("GET", "/api/domain-lists", r._handle_domain_lists_list)
        self._router.add("POST", "/api/domain-lists", r._handle_domain_list_create)
        self._router.add_prefix("GET", "/api/domain-lists/", r._handle_domain_list_get)
        self._router.add_prefix("POST", "/api/domain-lists/", r._handle_domain_list_post)
        self._router.add_prefix("DELETE", "/api/domain-lists/", r._handle_domain_list_delete)

        self._router.add("GET", "/api/proxy-sources", s._handle_proxy_sources_list)
        self._router.add("POST", "/api/proxy-sources", s._handle_proxy_source_create)
        self._router.add("POST", "/api/proxy-sources/fetch", s._handle_proxy_sources_fetch)
        self._router.add("GET", "/api/proxy-sources/progress", s._handle_proxy_sources_progress)
        self._router.add_prefix("GET", "/api/proxy-sources/", s._handle_proxy_source_get)
        self._router.add_prefix("POST", "/api/proxy-sources/", s._handle_proxy_source_post)
        self._router.add_prefix("DELETE", "/api/proxy-sources/", s._handle_proxy_source_delete)

        self._router.add("GET", "/api/ip-blacklists", s._handle_ip_blacklists_list)
        self._router.add("POST", "/api/ip-blacklists", s._handle_ip_blacklist_create)
        self._router.add("POST", "/api/ip-blacklists/fetch", s._handle_ip_blacklists_fetch)
        self._router.add("GET", "/api/ip-blacklists/progress", s._handle_ip_blacklists_progress)
        self._router.add_prefix("GET", "/api/ip-blacklists/", s._handle_ip_blacklist_get)
        self._router.add_prefix("POST", "/api/ip-blacklists/", s._handle_ip_blacklist_post)
        self._router.add_prefix("DELETE", "/api/ip-blacklists/", s._handle_ip_blacklist_delete)
        self._router.add("GET", "/api/ip-blacklist/entries", s._handle_ip_blacklist_entries)
        self._router.add("GET", "/api/ip-blacklist/matches", s._handle_ip_blacklist_matches)

        self._router.add("GET", "/api/blocklists", s._handle_blocklists_list)
        self._router.add("POST", "/api/blocklists", s._handle_blocklist_create)
        self._router.add("POST", "/api/blocklists/fetch", s._handle_blocklists_fetch)
        self._router.add("GET", "/api/blocklists/progress", s._handle_blocklists_progress)
        self._router.add_prefix("GET", "/api/blocklists/", s._handle_blocklist_get)
        self._router.add_prefix("POST", "/api/blocklists/", s._handle_blocklist_post)
        self._router.add_prefix("DELETE", "/api/blocklists/", s._handle_blocklist_delete)

        self._router.add("GET", "/api/custom-proxies", s._handle_custom_proxies_list)
        self._router.add("POST", "/api/custom-proxies", s._handle_custom_proxy_create)
        self._router.add("POST", "/api/custom-proxies/test-direct", s._handle_custom_proxy_test_direct)
        self._router.add_prefix("GET", "/api/custom-proxies/", s._handle_custom_proxy_get)
        self._router.add_prefix("POST", "/api/custom-proxies/", s._handle_custom_proxy_post)
        self._router.add_prefix("DELETE", "/api/custom-proxies/", s._handle_custom_proxy_delete)

        self._router.add("GET", "/api/schedules", a._handle_schedules_list)
        self._router.add("POST", "/api/schedules", a._handle_schedule_create)
        self._router.add_prefix("GET", "/api/schedules/status", a._handle_schedules_status)
        self._router.add_prefix("GET", "/api/schedules/log", a._handle_schedules_log)
        self._router.add("POST", "/api/schedules/pause", a._handle_schedules_pause)
        self._router.add("POST", "/api/schedules/resume", a._handle_schedules_resume)
        self._router.add("POST", "/api/schedules/restore-defaults", a._handle_schedules_restore_defaults)
        self._router.add_prefix("POST", "/api/schedules/", a._handle_schedule_post_subpath)
        self._router.add_prefix("DELETE", "/api/schedules/", a._handle_schedule_delete)

        self._router.add("GET", "/api/canary/status", a._handle_canary_status)
        self._router.add_prefix("GET", "/api/canary/history", a._handle_canary_history)
        self._router.add("POST", "/api/canary/hosts", a._handle_canary_hosts)
