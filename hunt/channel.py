"""Channel mixin — route the engine's own internet access through an upstream
proxy (the "channel").

In a network without a direct gateway, every outbound connection the engine
makes (downloading lists, checking proxies, measuring speed, resolving geo,
canary monitoring) must go through a corporate/external proxy selected by the
operator. This mixin provides:

* ``_resolve_channel()`` — current channel route (``""``/``"direct"``/
  ``"proxy:<addr>"``/``"custom:<id>"``).
* ``_outbound_connect(host, port, use_ssl, server_hostname, timeout)`` — an
  ``asyncio.open_connection`` drop-in that tunnels through the channel proxy
  when one is selected, otherwise connects directly.
* ``_channel_curl_proxy()`` — a ``--proxy`` string for curl-based downloads.
* ``get_channel_status()`` / ``set_channel(route)`` — API-facing helpers.

The channel is independent of the client-traffic ``active_proxy_addr`` so that
selecting a channel for the engine does not change how ProxyRunner forwards
user traffic.
"""

import asyncio

from hunt.conn import socks5_connect, socks4_connect, http_connect


class ChannelMixin:
    # route: "" | "direct" | "proxy:<addr>" | "custom:<id>"
    # "pool" is intentionally not supported for the engine (it would recurse:
    # checking pool proxies via the pool itself).

    def __init_channel(self):
        if not hasattr(self, "_channel_proxy_cache"):
            self._channel_proxy_cache = None
            self._channel_proxy_cache_route = None

    def _channel_proxy(self, route: str) -> dict | None:
        if not route or route == "direct":
            return None
        if route.startswith("proxy:"):
            addr = route[6:]
            r = self.ratings.get(addr)
            if not r or r.in_blacklist:
                return None
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                return None
            return {
                "protocol": r.protocol or "http",
                "host": host, "port": port,
                "username": "", "password": "",
            }
        if route.startswith("custom:"):
            proxy = self.get_custom_proxy_raw(route[7:])
            if not proxy or not proxy.get("enabled"):
                return None
            return {
                "protocol": proxy.get("protocol", "socks5"),
                "host": proxy["host"], "port": int(proxy["port"]),
                "username": proxy.get("username", "") or "",
                "password": proxy.get("password", "") or "",
            }
        return None

    def _channel_proxy_cached(self) -> dict | None:
        """Resolve the active channel proxy, cached until the route changes.

        Avoids a blocking DB read on every _outbound_connect for custom
        channels; the cache is invalidated by set_channel().
        """
        self.__init_channel()
        route = self._resolve_channel()
        if route != self._channel_proxy_cache_route:
            self._channel_proxy_cache_route = route
            self._channel_proxy_cache = self._channel_proxy(route)
        return self._channel_proxy_cache

    def _resolve_channel(self) -> str:
        route = getattr(self, "_channel_route", "") or ""
        if route == "pool":
            return ""
        return route

    def _channel_is_set(self) -> bool:
        """True if the operator selected a non-direct channel route."""
        route = self._resolve_channel()
        return bool(route) and route != "direct"

    async def _outbound_connect(self, host: str, port: int, *,
                                use_ssl: bool = False,
                                server_hostname: str | None = None,
                                timeout: float | None = None):
        """Open a connection to (host, port), tunneled through the channel proxy.

        ``use_ssl`` wraps TLS around the connection to the peer at (host, port)
        — i.e. the proxy being tested (for HTTPS proxies) or an HTTPS target.
        Returns (reader, writer) or raises on failure.

        Fail-closed: if a channel route is selected but the proxy can no longer
        be resolved (blacklisted/missing/disabled), this raises OSError rather
        than silently falling back to a direct connection — critical for the
        no-direct-gateway deployment this feature targets.
        """
        route = self._resolve_channel()
        proxy = self._channel_proxy_cached()
        to = 15 if timeout is None else timeout

        if proxy is None:
            if route and route != "direct":
                raise OSError(
                    f"channel proxy unavailable (route={route}): "
                    f"blacklisted, missing or disabled")
            conn_kwargs = {}
            if use_ssl:
                ctx = self._make_ssl_ctx()
                conn_kwargs["ssl"] = ctx
                conn_kwargs["server_hostname"] = server_hostname or host
            return await asyncio.wait_for(
                asyncio.open_connection(host, port, **conn_kwargs), timeout=to)

        phost = proxy["host"]
        pport = proxy["port"]
        proto = proxy.get("protocol", "socks5")
        uname = proxy.get("username", "")
        passwd = proxy.get("password", "")
        proxy_is_tls = (proto == "https")

        conn_kwargs = {}
        if proxy_is_tls:
            ctx = self._make_ssl_ctx()
            conn_kwargs["ssl"] = ctx
            conn_kwargs["server_hostname"] = phost
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(phost, pport, **conn_kwargs), timeout=to)

        ok = False
        if proto == "socks5":
            ok = await socks5_connect(reader, writer, host, port, uname, passwd)
        elif proto == "socks4":
            ok = await socks4_connect(reader, writer, host, port)
        else:
            ok = await http_connect(reader, writer, host, port, uname, passwd)
        if not ok:
            try:
                writer.close()
            except Exception:
                pass
            raise OSError(f"channel proxy handshake failed: {route}")

        if use_ssl:
            ctx = self._make_ssl_ctx()
            loop = asyncio.get_running_loop()
            transport = writer.transport
            protocol = transport.get_protocol()
            new_transport = await loop.start_tls(
                transport, protocol, ctx,
                server_hostname=server_hostname or host)
            writer = asyncio.StreamWriter(new_transport, protocol, reader, loop)
        return reader, writer

    def _channel_curl_proxy(self) -> str:
        """Return a curl --proxy string for the active channel, or ""."""
        route = self._resolve_channel()
        proxy = self._channel_proxy(route)
        if not proxy:
            return ""
        proto = proxy.get("protocol", "socks5")
        host = proxy["host"]
        port = proxy["port"]
        uname = proxy.get("username", "")
        passwd = proxy.get("password", "")
        scheme = {
            "socks5": "socks5h",
            "socks4": "socks4a",
            "http": "http",
            "https": "http",
        }.get(proto, "socks5h")
        auth = ""
        if uname:
            from urllib.parse import quote
            auth = f"{quote(uname, safe='')}:{quote(passwd, safe='')}@"
        return f"{scheme}://{auth}{host}:{port}"

    def get_channel_status(self) -> dict:
        route = getattr(self, "_channel_route", "") or ""
        proxy = self._channel_proxy_cached() if (route and route != "direct") else None
        available = proxy is not None
        info = None
        if proxy:
            info = {
                "route": route,
                "protocol": proxy.get("protocol", ""),
                "host": proxy["host"],
                "port": proxy["port"],
                "has_auth": bool(proxy.get("username")),
            }
        return {
            "channel_route": route,
            "proxy": info,
            "available": available if route else True,
            "channel_tls_trusted": getattr(self, "_channel_tls_trusted", None),
        }

    def set_channel(self, route: str):
        if route == "pool":
            route = ""
        self._channel_route = route or ""
        # Invalidate the resolved-proxy cache so the next lookup re-reads it.
        self.__init_channel()
        self._channel_proxy_cache_route = None
        self._channel_proxy_cache = None
        # Reset the channel TLS-trust baseline; recomputed lazily.
        self._channel_tls_trusted = None
        self._routing_set("channel_route", self._channel_route)
        self._emit(f"Channel set to: {route or 'direct'}", "info")
