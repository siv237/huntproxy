"""Functional split of the huntproxy backend."""

import asyncio
import time
from hunt.constants import logger

class CheckSpeedMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    _SPEED_READ_TIMEOUT = 8.0
    _SPEED_GRACE = 3.0
    _SPEED_FLOOR = 5.0
    _SPEED_HARD_CAP = 20.0
    async def _measure_speed(self, host: str, port: int, is_socks: bool = False, use_ssl: bool = False, supports_connect: bool = False, on_active=None) -> float:
            # A separate, small semaphore bounds concurrent speed measurements
            # across the whole cycle. Without it, every proxy in a 100–300
            # wide check wave hits the same speed server at once, so the
            # server rate-limits the shared egress and every proxy gets ~1/N
            # of its real throughput — the measurement reflects server
            # contention, not the proxy's capacity.
            servers = list(self.SPEED_SERVERS)
            offset = self._speed_server_idx % len(servers) if servers else 0
            self._speed_server_idx += 1
            ordered = servers[offset:] + servers[:offset]
            async with self._speed_sem:
                if on_active is not None:
                    try:
                        on_active()
                    except Exception:
                        logger.debug("suppressed", exc_info=True)
                # Overall deadline across all servers/attempts — without this, a
                # slow-drip proxy that trickles data can hang across multiple
                # speed servers for many minutes, blocking the entire check cycle.
                overall_deadline = time.monotonic() + 45
                for srv_host, srv_path, expected_size in ordered:
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
                        logger.debug("suppressed", exc_info=True)
                    return None
            return r, w


    async def _speed_single(self, host: str, port: int, is_socks: bool,
                                 srv_host: str, srv_path: str, expected_size: int,
                                 use_ssl: bool = False, supports_connect: bool = False) -> float:
            speed = await self._try_speed(host, port, is_socks, use_ssl, self._direct_speed_single, srv_host, srv_path, expected_size)
            if speed > 0:
                return speed
            if not use_ssl:
                return 0.0
            speed = await self._try_speed(host, port, is_socks, use_ssl, self._http_connect_speed_single, srv_host, srv_path, expected_size)
            if speed > 0:
                return speed
            if supports_connect:
                return await self._try_speed(host, port, is_socks, use_ssl, self._https_speed_single, srv_host, srv_path, expected_size)
            return 0.0

    async def _try_speed(self, host, port, is_socks, use_ssl, speed_fn, *args) -> float:
        w = None
        try:
            conn = await self._speed_open(host, port, is_socks, use_ssl)
            if conn is None:
                return 0.0
            r, w = conn
            return await speed_fn(r, w, *args)
        except Exception:
            return 0.0
        finally:
            try:
                if w is not None:
                    w.close()
                    await w.wait_closed()
            except Exception:
                logger.debug("suppressed", exc_info=True)


    async def _direct_speed_single(self, r, w, srv_host: str, srv_path: str, expected_size: int) -> float:
            """Send a plain HTTP GET through the existing connection.

            Works for plain HTTP proxies, HTTPS proxies, and SOCKS tunnels.
            """
            try:
                req = (
                    f"GET http://{srv_host}{srv_path} HTTP/1.0\r\n"
                    f"Host: {srv_host}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                )
                w.write(req.encode())
                await asyncio.wait_for(w.drain(), timeout=10)
                return await self._read_speed_stream(r, expected_size)
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
            tls_w = None
            try:
                if not await self._https_connect_tunnel(r, w, srv_host):
                    return 0.0
                tls_w = await self._https_tls_upgrade(r, w, srv_host)
                if tls_w is None:
                    return 0.0
                return await self._https_read_speed(r, tls_w, srv_host, srv_path, expected_size)
            except Exception:
                return 0.0
            finally:
                if tls_w is not None:
                    try:
                        tls_w.close()
                        await tls_w.wait_closed()
                    except Exception:
                        logger.debug("suppressed", exc_info=True)

    async def _https_connect_tunnel(self, r, w, srv_host) -> bool:
        req = f"CONNECT {srv_host}:443 HTTP/1.1\r\nHost: {srv_host}:443\r\n\r\n"
        w.write(req.encode())
        await asyncio.wait_for(w.drain(), timeout=self.effective_timeout)
        try:
            resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
        except Exception:
            return False
        return b"200" in resp.split(b"\r\n")[0]

    async def _https_tls_upgrade(self, r, w, srv_host):
        ctx = self._make_ssl_ctx()
        loop = asyncio.get_running_loop()
        transport = w.transport
        protocol = transport.get_protocol()
        try:
            new_transport = await loop.start_tls(transport, protocol, ctx, server_hostname=srv_host)
        except Exception:
            return None
        return asyncio.StreamWriter(new_transport, protocol, r, loop)

    async def _https_read_speed(self, r, tls_w, srv_host, srv_path, expected_size) -> float:
        try:
            req = f"GET {srv_path} HTTP/1.0\r\nHost: {srv_host}\r\nConnection: close\r\n\r\n"
            tls_w.write(req.encode())
            await asyncio.wait_for(tls_w.drain(), timeout=10)
            return await self._read_speed_stream(r, expected_size)
        except Exception:
            return 0.0

    async def _read_speed_stream(self, reader, expected_size: int) -> float:
        """Stream-download with real-time early bail.

        Instead of holding a speed slot for the full 30s deadline on a
        slow-drip proxy, measure the running throughput and abort early once
        the proxy is clearly hopeless (below _SPEED_FLOOR KB/s after
        _SPEED_GRACE seconds). Returns the measured KB/s — even if we bailed,
        the rate at which data arrived is a valid signal for scoring.
        """
        t0 = time.monotonic()
        deadline = t0 + self._SPEED_HARD_CAP
        total = 0
        http_ok = True
        headers_done = False
        while True:
            if time.monotonic() >= deadline:
                break
            try:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=self._SPEED_READ_TIMEOUT)
            except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                break
            if not chunk:
                break
            if not headers_done:
                end = chunk.find(b"\r\n\r\n")
                if end != -1:
                    headers_done = True
                    parts = chunk[:end].split(b"\r\n", 1)[0].split(b" ", 2)
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
            if elapsed > self._SPEED_GRACE and total > 0:
                if (total / elapsed) / 1024.0 < self._SPEED_FLOOR:
                    break
        elapsed = time.monotonic() - t0
        if http_ok and total > 0 and elapsed > 0:
            return (total / elapsed) / 1024.0
        return 0.0

