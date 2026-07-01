"""Functional split of the huntproxy backend."""

import asyncio
import json
import ssl as _ssl
import time
from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating

class CheckSpeedMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    async def _measure_speed(self, host: str, port: int, is_socks: bool = False, use_ssl: bool = False, supports_connect: bool = False) -> float:
            # Overall deadline across all servers/attempts — without this, a
            # slow-drip proxy that trickles data can hang across multiple
            # speed servers for many minutes, blocking the entire check cycle.
            overall_deadline = time.monotonic() + 45
            for srv_host, srv_path, expected_size in self.SPEED_SERVERS:
                remaining = overall_deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    speed = await asyncio.wait_for(
                        self._speed_single(host, port, is_socks, srv_host, srv_path, expected_size, use_ssl, supports_connect),
                        timeout=remaining,
                    )
                except asyncio.TimeoutError:
                    break
                if speed > 0:
                    return speed
            return 0.0


    async def _speed_open(self, host: str, port: int, is_socks: bool, use_ssl: bool) -> tuple:
            """Open a fresh connection for a speed measurement attempt."""
            r, w = await self._outbound_connect(
                host, port, use_ssl=use_ssl, server_hostname=host, timeout=self.effective_timeout)
            if is_socks:
                if port == 4145:
                    ok = await self._socks4_test(r, w)
                else:
                    ok = await self._socks5_test(r, w)
                if not ok:
                    w.close()
                    try:
                        await w.wait_closed()
                    except Exception:
                        pass
                    return None
            return r, w


    async def _speed_single(self, host: str, port: int, is_socks: bool,
                                 srv_host: str, srv_path: str, expected_size: int,
                                 use_ssl: bool = False, supports_connect: bool = False) -> float:
            # Attempt 1: direct HTTP GET over the connection.
            w = None
            try:
                conn = await self._speed_open(host, port, is_socks, use_ssl)
                if conn is None:
                    return 0.0
                r, w = conn
                speed = await self._direct_speed_single(r, w, srv_host, srv_path, expected_size)
                if speed > 0:
                    return speed
            except Exception:
                pass
            finally:
                try:
                    if w is not None:
                        w.close()
                        await w.wait_closed()
                except Exception:
                    pass

            # Attempt 2: for HTTPS proxies, try plain HTTP inside a CONNECT tunnel.
            if use_ssl:
                w = None
                try:
                    conn = await self._speed_open(host, port, is_socks, use_ssl)
                    if conn is None:
                        return 0.0
                    r, w = conn
                    speed = await self._http_connect_speed_single(r, w, srv_host, srv_path, expected_size)
                    if speed > 0:
                        return speed
                except Exception:
                    pass
                finally:
                    try:
                        if w is not None:
                            w.close()
                            await w.wait_closed()
                    except Exception:
                        pass

                # Attempt 3: real HTTPS tunnel (CONNECT to 443 + TLS).
                if supports_connect:
                    w = None
                    try:
                        conn = await self._speed_open(host, port, is_socks, use_ssl)
                        if conn is None:
                            return 0.0
                        r, w = conn
                        return await self._https_speed_single(r, w, srv_host, srv_path, expected_size)
                    except Exception:
                        pass
                    finally:
                        try:
                            if w is not None:
                                w.close()
                                await w.wait_closed()
                        except Exception:
                            pass
            return 0.0


    async def _direct_speed_single(self, r, w, srv_host: str, srv_path: str, expected_size: int) -> float:
            """Send a plain HTTP GET through the existing connection.

            Works for plain HTTP proxies, HTTPS proxies, and SOCKS tunnels.
            """
            try:
                t0 = time.monotonic()
                req = (
                    f"GET http://{srv_host}{srv_path} HTTP/1.0\r\n"
                    f"Host: {srv_host}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                )
                w.write(req.encode())
                await asyncio.wait_for(w.drain(), timeout=10)
                total = 0
                http_ok = True
                speed_deadline = time.monotonic() + 30
                while True:
                    remaining = speed_deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        chunk = await asyncio.wait_for(r.read(65536), timeout=min(30, remaining))
                    except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                        break
                    if not chunk:
                        break
                    if http_ok and total == 0:
                        end = chunk.find(b"\r\n\r\n")
                        if end != -1:
                            head = chunk[:end]
                            status_line = head.split(b"\r\n", 1)[0]
                            parts = status_line.split(b" ", 2)
                            try:
                                code = int(parts[1]) if len(parts) >= 2 else 0
                            except Exception:
                                code = 0
                            if not (200 <= code < 400):
                                http_ok = False
                            chunk = chunk[end + 4:]
                    total += len(chunk)
                    if total >= expected_size:
                        break
                elapsed = time.monotonic() - t0
                if elapsed > 0 and http_ok and total >= expected_size * 0.8:
                    return total / elapsed / 1024.0
                return 0.0
            except Exception:
                return 0.0


    async def _http_connect_speed_single(self, r, w, srv_host: str, srv_path: str, expected_size: int) -> float:
            """HTTP download through a CONNECT tunnel to the target's port 80.

            For HTTPS proxies that do not accept plain HTTP GET over TLS, we can
            usually establish a CONNECT tunnel and send a plain HTTP request
            inside it. This works with the existing HTTP speed servers.
            """
            try:
                req = f"CONNECT {srv_host}:80 HTTP/1.1\r\nHost: {srv_host}:80\r\n\r\n"
                w.write(req.encode())
                await asyncio.wait_for(w.drain(), timeout=self.effective_timeout)
                try:
                    resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
                    if b"200" not in resp.split(b"\r\n")[0]:
                        return 0.0
                except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                    return 0.0
                return await self._direct_speed_single(r, w, srv_host, srv_path, expected_size)
            except Exception:
                return 0.0


    async def _https_speed_single(self, r, w, srv_host: str, srv_path: str, expected_size: int) -> float:
            """HTTPS download through a CONNECT (or SOCKS) tunnel.

            The reader/writer are already connected to the upstream proxy and the
            tunnel is established. We then upgrade the tunnel to TLS and perform a
            GET over HTTPS. This measures real SSL throughput and avoids HTTP-to-HTTPS
            redirects that break plain HTTP speed tests.
            """
            tls_w = None
            try:
                req = f"CONNECT {srv_host}:443 HTTP/1.1\r\nHost: {srv_host}:443\r\n\r\n"
                w.write(req.encode())
                await asyncio.wait_for(w.drain(), timeout=self.effective_timeout)
                try:
                    resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
                    if b"200" not in resp.split(b"\r\n")[0]:
                        return 0.0
                except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                    return 0.0

                # Upgrade the tunnel to TLS.
                ctx = self._make_ssl_ctx()
                loop = asyncio.get_running_loop()
                transport = w.transport
                protocol = transport.get_protocol()
                try:
                    new_transport = await loop.start_tls(transport, protocol, ctx, server_hostname=srv_host)
                except Exception:
                    return 0.0
                # After start_tls the old StreamWriter points to the closed
                # transport; create a new writer over the upgraded transport.
                tls_w = asyncio.StreamWriter(new_transport, protocol, r, loop)

                t0 = time.monotonic()
                req = (
                    f"GET {srv_path} HTTP/1.0\r\n"
                    f"Host: {srv_host}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                )
                tls_w.write(req.encode())
                await asyncio.wait_for(tls_w.drain(), timeout=10)
                total = 0
                http_ok = True
                speed_deadline = time.monotonic() + 30
                while True:
                    remaining = speed_deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        chunk = await asyncio.wait_for(r.read(65536), timeout=min(30, remaining))
                    except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                        break
                    if not chunk:
                        break
                    if http_ok and total == 0:
                        end = chunk.find(b"\r\n\r\n")
                        if end != -1:
                            head = chunk[:end]
                            status_line = head.split(b"\r\n", 1)[0]
                            parts = status_line.split(b" ", 2)
                            try:
                                code = int(parts[1]) if len(parts) >= 2 else 0
                            except Exception:
                                code = 0
                            if not (200 <= code < 400):
                                http_ok = False
                            chunk = chunk[end + 4:]
                    total += len(chunk)
                    if total >= expected_size:
                        break
                elapsed = time.monotonic() - t0
                if elapsed > 0 and http_ok and total >= expected_size * 0.8:
                    return total / elapsed / 1024.0
                return 0.0
            except Exception:
                return 0.0
            finally:
                if tls_w is not None:
                    try:
                        tls_w.close()
                        await tls_w.wait_closed()
                    except Exception:
                        pass

