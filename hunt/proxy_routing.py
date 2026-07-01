"""Proxy route selection — extracted from proxy_runner.py."""
import asyncio
import base64
import socket
import struct
import time
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.models import ProxyRating
from typing import Optional

class ProxyRouteMixin:
    async def _connect_upstream(self, host: str, port: int, need_connect: bool = True):
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
            try:
                if self.state._channel_is_set():
                    reader, writer = await self.state._outbound_connect(host, port, timeout=15)
                    chain.append(f"direct via channel")
                else:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=15)
                    chain.append("direct")
                return reader, writer, False
            except Exception:
                return None

        if route.startswith("custom:"):
            proxy_id = route[7:]
            proxy = self.state.get_custom_proxy_raw(proxy_id)
            if not proxy or not proxy["enabled"]:
                chain.append(f"custom:{proxy_id} (disabled)")
                default = self.state._routing_get("default_route", "direct")
                return await self._connect_by_route(default, host, port, chain, need_connect)
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(proxy["host"], proxy["port"]), timeout=10)
            except Exception:
                return None
            protocol = proxy.get("protocol", "socks5")
            uname = proxy.get("username", "")
            passwd = proxy.get("password", "")
            if protocol == "socks5":
                ok = await self._socks5_cmd_auth(reader, writer, host, port, uname, passwd)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"custom:{proxy_id}")
                return reader, writer, False
            else:
                if need_connect:
                    ok = await self._http_connect_cmd_auth(reader, writer, host, port, uname, passwd)
                    if not ok:
                        try: writer.close()
                        except: pass
                        return None
                    chain.append(f"custom:{proxy_id}")
                    return reader, writer, False
                else:
                    chain.append(f"custom:{proxy_id}")
                    return reader, writer, True

        if route.startswith("proxy:"):
            addr = route[6:]
            r = self.state.ratings.get(addr)
            # Manual blacklist is a hard exclusion; IP blacklist only lowers score.
            if not r or r.in_blacklist:
                return None
            phost, pport_str = r.address.rsplit(":", 1)
            try:
                conn_kwargs = {}
                if r.ssl_supported:
                    ctx = self.state._make_ssl_ctx()
                    conn_kwargs["ssl"] = ctx
                    conn_kwargs["server_hostname"] = phost
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
            except Exception:
                return None
            if r.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            elif r.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            else:
                if need_connect:
                    ok = await self._http_connect_cmd(reader, writer, host, port)
                    if not ok:
                        try: writer.close()
                        except: pass
                        return None
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, False
                else:
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, True

        if route == "pool" or route == "":
            pool = [r for r in self.state.ratings.values()
                    if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
            if need_connect:
                pool = [r for r in pool if r.supports_connect or r.protocol in ("socks4", "socks5")]
            if not pool:
                return None
            pool.sort(key=lambda r: r.score, reverse=True)
            for attempt in range(min(len(pool), 8)):
                p = pool[attempt]
                phost, pport_str = p.address.rsplit(":", 1)
                try:
                    conn_kwargs = {}
                    if p.ssl_supported:
                        ctx = self.state._make_ssl_ctx()
                        conn_kwargs["ssl"] = ctx
                        conn_kwargs["server_hostname"] = phost
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
                except Exception:
                    continue
                ok = False
                if p.protocol == "socks4":
                    ok = await self._socks4_cmd(reader, writer, host, port)
                elif p.protocol == "socks5":
                    ok = await self._socks5_cmd(reader, writer, host, port)
                else:
                    if need_connect:
                        ok = await self._http_connect_cmd(reader, writer, host, port)
                    else:
                        ok = True
                if not ok:
                    try: writer.close()
                    except: pass
                    continue
                self._failover_idx = (attempt + 1) % len(pool)
                chain.append(f"pool:{p.address}")
                is_raw = (not need_connect and p.protocol not in ("socks4", "socks5"))
                return reader, writer, is_raw
            return None

        if self.direct_mode:
            try:
                if self.state._channel_is_set():
                    reader, writer = await self.state._outbound_connect(host, port, timeout=15)
                    chain.append(f"direct via channel")
                else:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=15)
                    chain.append("direct")
                return reader, writer, False
            except Exception:
                return None

        if self.active_proxy_addr:
            r = self.state.ratings.get(self.active_proxy_addr)
            if not r or r.in_blacklist:
                return None
            phost, pport_str = r.address.rsplit(":", 1)
            try:
                conn_kwargs = {}
                if r.ssl_supported:
                    ctx = self.state._make_ssl_ctx()
                    conn_kwargs["ssl"] = ctx
                    conn_kwargs["server_hostname"] = phost
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
            except Exception:
                return None
            if r.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            elif r.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
                if not ok:
                    try: writer.close()
                    except: pass
                    return None
                chain.append(f"proxy:{r.address}")
                return reader, writer, False
            else:
                if need_connect:
                    ok = await self._http_connect_cmd(reader, writer, host, port)
                    if not ok:
                        try: writer.close()
                        except: pass
                        return None
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, False
                else:
                    chain.append(f"proxy:{r.address}")
                    return reader, writer, True

        pool = [r for r in self.state.ratings.values()
                if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
        if need_connect:
            pool = [r for r in pool if r.supports_connect or r.protocol in ("socks4", "socks5")]
        if not pool:
            return None
        pool.sort(key=lambda r: r.score, reverse=True)
        for attempt in range(min(len(pool), 8)):
            p = pool[attempt]
            phost, pport_str = p.address.rsplit(":", 1)
            try:
                conn_kwargs = {}
                if p.ssl_supported:
                    ctx = self.state._make_ssl_ctx()
                    conn_kwargs["ssl"] = ctx
                    conn_kwargs["server_hostname"] = phost
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(phost, int(pport_str), **conn_kwargs), timeout=10)
            except Exception:
                continue
            ok = False
            if p.protocol == "socks4":
                ok = await self._socks4_cmd(reader, writer, host, port)
            elif p.protocol == "socks5":
                ok = await self._socks5_cmd(reader, writer, host, port)
            else:
                if need_connect:
                    ok = await self._http_connect_cmd(reader, writer, host, port)
                else:
                    ok = True
            if not ok:
                try: writer.close()
                except: pass
                continue
            self._failover_idx = (attempt + 1) % len(pool)
            chain.append(f"pool:{p.address}")
            is_raw = (not need_connect and p.protocol not in ("socks4", "socks5"))
            return reader, writer, is_raw
        return None



