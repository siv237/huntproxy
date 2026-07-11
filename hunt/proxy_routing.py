"""Proxy route selection — extracted from proxy_runner.py."""
import asyncio
from hunt.models import ProxyRating
import logging

logger = logging.getLogger(__name__)

_CONNECT_RETRIES = 3
_RETRY_DELAY = 0.3

class ProxyRouteMixin:
    def _is_self_target(self, host: str, port: int) -> bool:
        host = (host or "").lower()
        if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0", "[::1]", ""):
            ports = {self.port}
            for attr in ("_socks5_port", "_transparent_port", "_proxy_port"):
                p = getattr(self.state, attr, None)
                if isinstance(p, int):
                    ports.add(p)
            return port in ports
        return False

    async def _connect_upstream(self, host: str, port: int, need_connect: bool = True):
        if self._is_self_target(host, port):
            return None
        route = self.state._resolve_route(host)
        chain = []
        result = await self._connect_by_route(route, host, port, chain, need_connect)
        if result is None:
            return None
        reader, writer, is_raw_proxy = result
        return reader, writer, chain, is_raw_proxy

    async def _connect_by_route(self, route: str, host: str, port: int, chain: list = None, need_connect: bool = True):
        if chain is None:
            chain = []
        if route == "direct":
            return await self._connect_direct(host, port, chain)
        if route.startswith("custom:"):
            return await self._connect_via_custom(route[7:], host, port, chain, need_connect)
        if route.startswith("proxy:"):
            addr = route[6:]
            result = await self._connect_via_addr(addr, host, port, chain, need_connect)
            if result is not None:
                return result
            self.state._record_traffic_fail(addr)
            chain.append(f"proxy:{addr} (fallback→pool)")
            return await self._connect_via_pool(host, port, chain, need_connect)
        if route == "pool" or route == "":
            return await self._connect_via_pool(host, port, chain, need_connect)
        # Fallback: direct mode or active proxy, then pool
        return await self._connect_fallback(host, port, chain, need_connect)

    async def _connect_direct(self, host: str, port: int, chain: list) -> tuple:
        try:
            if self.state._channel_is_set():
                reader, writer = await self.state._outbound_connect(host, port, timeout=15)
                chain.append("direct via channel")
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=15)
                chain.append("direct")
            return reader, writer, False
        except Exception:
            return None

    async def _connect_via_custom(self, proxy_id: str, host: str, port: int, chain: list, need_connect: bool) -> tuple:
        proxy = self.state.get_custom_proxy_raw(proxy_id)
        if not proxy or not proxy["enabled"]:
            chain.append(f"custom:{proxy_id} (disabled)")
            default = self.state._routing_get("default_route", "direct")
            return await self._connect_by_route(default, host, port, chain, need_connect)
        protocol = proxy.get("protocol", "socks5")
        uname = proxy.get("username", "")
        passwd = proxy.get("password", "")
        for attempt in range(_CONNECT_RETRIES):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(proxy["host"], proxy["port"]), timeout=10)
            except Exception:
                if attempt < _CONNECT_RETRIES - 1:
                    await asyncio.sleep(_RETRY_DELAY)
                continue
            if protocol == "socks5":
                ok = await self._socks5_cmd_auth(reader, writer, host, port, uname, passwd)
            elif need_connect:
                ok = await self._http_connect_cmd_auth(reader, writer, host, port, uname, passwd)
            else:
                chain.append(f"custom:{proxy_id}")
                return reader, writer, True
            if ok:
                tag = f" (retry:{attempt})" if attempt else ""
                chain.append(f"custom:{proxy_id}{tag}")
                return reader, writer, False
            self._safe_close(writer)
            if attempt < _CONNECT_RETRIES - 1:
                await asyncio.sleep(_RETRY_DELAY)
        return None

    async def _connect_via_addr(self, addr: str, host: str, port: int, chain: list, need_connect: bool) -> tuple:
        r = self.state.ratings.get(addr)
        if not r or r.in_blacklist:
            return None
        return await self._connect_via_rating(r, host, port, chain, need_connect)

    async def _connect_via_rating(self, r: ProxyRating, host: str, port: int, chain: list, need_connect: bool) -> tuple:
        for attempt in range(_CONNECT_RETRIES):
            reader, writer = await self._open_proxy_conn(r)
            if reader is None:
                if attempt < _CONNECT_RETRIES - 1:
                    await asyncio.sleep(_RETRY_DELAY)
                continue
            ok = await self._negotiate_proxy(r, reader, writer, host, port, need_connect)
            if ok:
                tag = f" (retry:{attempt})" if attempt else ""
                chain.append(f"proxy:{r.address}{tag}")
                is_raw = (not need_connect and r.protocol not in ("socks4", "socks5"))
                return reader, writer, is_raw
            self._safe_close(writer)
            if attempt < _CONNECT_RETRIES - 1:
                await asyncio.sleep(_RETRY_DELAY)
        return None

    async def _connect_via_pool(self, host: str, port: int, chain: list, need_connect: bool) -> tuple:
        pool = self._build_pool(need_connect)
        if not pool:
            return None
        for attempt in range(min(len(pool), 8)):
            p = pool[attempt]
            reader, writer = await self._open_proxy_conn(p)
            if reader is None:
                continue
            ok = await self._negotiate_proxy(p, reader, writer, host, port, need_connect)
            if not ok:
                self._safe_close(writer)
                continue
            self._failover_idx = (attempt + 1) % len(pool)
            chain.append(f"pool:{p.address}")
            is_raw = (not need_connect and p.protocol not in ("socks4", "socks5"))
            return reader, writer, is_raw
        return None

    async def _connect_fallback(self, host: str, port: int, chain: list, need_connect: bool) -> tuple:
        if self.direct_mode:
            return await self._connect_direct(host, port, chain)
        if self.active_proxy_addr:
            result = await self._connect_via_addr(self.active_proxy_addr, host, port, chain, need_connect)
            if result is not None:
                return result
            self.state._record_traffic_fail(self.active_proxy_addr)
            chain.append(f"proxy:{self.active_proxy_addr} (fallback→pool)")
        return await self._connect_via_pool(host, port, chain, need_connect)

    def _build_pool(self, need_connect: bool) -> list:
        pool = [r for r in self.state.ratings.values()
                if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
        if need_connect:
            pool = [r for r in pool if r.supports_connect or r.protocol in ("socks4", "socks5")]
        pool.sort(key=lambda r: r.score, reverse=True)
        return pool

    async def _open_proxy_conn(self, r: ProxyRating):
        phost, pport_str = r.address.rsplit(":", 1)
        try:
            conn_kwargs = {}
            if r.ssl_supported:
                ctx = self.state._make_ssl_ctx()
                conn_kwargs["ssl"] = ctx
                conn_kwargs["server_hostname"] = phost
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
            return reader, writer
        except Exception:
            return None, None

    async def _negotiate_proxy(self, r: ProxyRating, reader, writer, host: str, port: int, need_connect: bool) -> bool:
        if r.protocol == "socks4":
            return await self._socks4_cmd(reader, writer, host, port)
        if r.protocol == "socks5":
            return await self._socks5_cmd(reader, writer, host, port)
        if need_connect:
            return await self._http_connect_cmd(reader, writer, host, port)
        return True

    def _safe_close(self, writer):
        try:
            writer.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)
