"""Functional split of the huntproxy backend."""

import asyncio
import json
import time
from hunt.constants import logger
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating

class CheckingMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})

    @staticmethod
    def _is_socks_addr(addr: str) -> bool:
            try:
                _, port_str = addr.rsplit(":", 1)
                return int(port_str) in CheckingMixin._SOCKS_PORTS
            except Exception:
                return False

    async def _validate_all(self, proxies: set):
            sem = asyncio.Semaphore(self.parallel)
            lock = asyncio.Lock()
            ok_count = 0
            fail_count = 0
            self._fail_streak = 0
            self._check_streak = 0
            _ctr = [0]

            async def check_one(addr: str):
                nonlocal ok_count, fail_count
                wid = _ctr[0]; _ctr[0] += 1
                try:
                    _p = int(addr.rsplit(":", 1)[1])
                    _proto = "socks5" if _p in (1080, 10808, 9050) else "socks4" if _p == 4145 else "http"
                except Exception:
                    _proto = "http"
                self._active_checks[wid] = {"addr": addr, "step": "queued", "started": time.time(), "protocol": _proto}
                try:
                    while True:
                        if self._paused:
                            await self._pause_event.wait()
                        if addr in self.blacklist:
                            async with lock:
                                if getattr(self, '_health_running', False):
                                    return
                                self.checked += 1
                            return
                        self._active_checks[wid] = {"addr": addr, "step": "queued", "started": time.time(), "protocol": _proto}
                        async with sem:
                            if self._internet_suspect:
                                await self._pause_event.wait()
                                continue
                            self._active_checks[wid] = {"addr": addr, "step": "connect", "started": time.time(), "protocol": _proto}
                            http_task = asyncio.create_task(self._check_proxy(addr))
                            ssl_task = asyncio.create_task(self._check_ssl(addr))
                            results = await asyncio.gather(http_task, ssl_task, return_exceptions=True)
                            if isinstance(results[0], Exception):
                                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = False, "", False, False, {}, {}, 0.0, "", False
                            else:
                                ok, country, supports_connect, mitm_suspect, egress, listen, http_latency, cc, fast_fail = results[0]
                            if isinstance(results[1], Exception):
                                ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = False, "", "", {}, 0.0, False
                            else:
                                ssl_ok, ssl_country, ssl_cc, ssl_egress, ssl_latency, ssl_supports_connect = results[1]
                            if fast_fail and not ok and not ssl_ok:
                                need_auto_pause = False
                                async with lock:
                                    if getattr(self, '_health_running', False):
                                        return
                                    self._fail_streak += 1
                                    self._check_streak += 1
                                    self.checked += 1
                                    fail_count += 1
                                    self.failed = fail_count
                                    if self._check_streak >= 3 and self._fail_streak / self._check_streak > 0.7:
                                        need_auto_pause = True
                                if need_auto_pause:
                                    await self._auto_pause_if_internet_down()
                                if self._internet_suspect:
                                    await self._pause_event.wait()
                                    continue
                                return
                            if not ok and ssl_ok:
                                ok = True
                                country = ssl_country
                                cc = ssl_cc
                                egress = ssl_egress
                                http_latency = ssl_latency
                                supports_connect = ssl_supports_connect
                            elif ok and not ssl_ok:
                                pass
                            elif ok and ssl_ok:
                                if not egress and ssl_egress:
                                    egress = ssl_egress
                                if not supports_connect and ssl_supports_connect:
                                    supports_connect = ssl_supports_connect
                            # Non-SOCKS proxies must support CONNECT to be useful for HTTPS.
                            if ok and not self._is_socks_addr(addr) and not supports_connect:
                                ok = False
                            speed = 0.0
                            if ok:
                                self._active_checks[wid] = {"addr": addr, "step": "speed", "started": time.time(), "protocol": _proto, "country": country, "cc": cc}
                                host, port_str = addr.rsplit(":", 1)
                                is_socks = port_str.isdigit() and int(port_str) in (1080, 10808, 9050, 4145)
                                use_ssl = ssl_ok and not is_socks
                                try:
                                    speed = await self._measure_speed(host, int(port_str), is_socks,
                                                                       use_ssl=use_ssl, supports_connect=supports_connect)
                                except Exception:
                                    speed = 0.0
                            async with lock:
                                if getattr(self, '_health_running', False):
                                    return
                                if self._internet_suspect:
                                    pass  # handle outside lock
                                else:
                                    self.checked += 1
                                    self._check_streak += 1
                                    if ok:
                                        ok_count += 1
                                        self.working = ok_count
                                        self.last_proxy = addr
                                        self.last_country = country
                                        self._fail_streak = 0
                                    else:
                                        fail_count += 1
                                        self.failed = fail_count
                                        self._fail_streak += 1
                                    self._update_rating(addr, ok, country, http_latency, supports_connect, mitm_suspect, egress, listen, speed, country_code=cc, ssl_supported=ssl_ok)
                                    if self.checked % 25 == 0 or ok:
                                        pct = int(100 * self.checked / max(1, self.checking_total))
                                        self._emit(
                                            f"{pct}% {self.checked}/{self.checking_total} | "
                                            f"working: {ok_count} | last: {addr} {country}",
                                            "progress"
                                        )
                                    if self._check_streak >= 10 and self._fail_streak / self._check_streak > 0.7:
                                        pass  # handle outside lock
                            if self._internet_suspect:
                                await self._pause_event.wait()
                                continue
                            if self._check_streak >= 10 and self._fail_streak / self._check_streak > 0.7:
                                await self._auto_pause_if_internet_down()
                            return
                finally:
                    self._active_checks.pop(wid, None)

            tasks = [asyncio.create_task(check_one(p)) for p in proxies]
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=len(proxies) * (self.timeout + 10) // max(1, self.parallel) + 60,
                )
            except asyncio.TimeoutError:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                self._emit("Validation timed out, cancelling stuck tasks", "warn")
            self._save_state()
            self._save_working_file()
            self._rating_updates_since_save = 0
            self._push_history()

    async def _check_proxy(self, addr: str) -> tuple:
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                return False, "", False, False, {}, {}, 0.0, "", False
            is_socks = port in (1080, 10808, 9050, 4145)

            t0 = time.monotonic()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=self.timeout,
                )
            except (asyncio.TimeoutError, OSError):
                elapsed = time.monotonic() - t0
                if elapsed < 0.3:
                    return False, "", False, False, {}, {}, 0.0, "", True
                return False, "", False, False, {}, {}, 0.0, "", False

            listen_task = asyncio.create_task(self._resolve_geo(host))
            country = ""
            country_code = ""
            supports_connect = False
            mitm_suspect = False
            egress: dict = {}

            if is_socks:
                if port == 4145:
                    ok = await self._socks4_test(reader, writer)
                else:
                    ok = await self._socks5_test(reader, writer)
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
                if not ok:
                    listen = await listen_task
                    return False, "", False, False, {}, listen, 0.0, "", False
                egress = await self._socks_egress(host, port)
                if egress:
                    country = egress.get("egress_country", "")
                    country_code = country_code_from_name(country)
                if not country:
                    country = "Unknown"
                supports_connect = True
                http_latency = time.monotonic() - t0
            else:
                try:
                    req = (
                        "GET http://ip-api.com/json/ HTTP/1.0\r\n"
                        "Host: ip-api.com\r\n"
                        "User-Agent: huntproxy\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    )
                    writer.write(req.encode())
                    await asyncio.wait_for(writer.drain(), timeout=self.timeout)
                    buf = b""
                    while True:
                        try:
                            chunk = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
                        except asyncio.TimeoutError:
                            break
                        if not chunk:
                            break
                        buf += chunk
                        if buf.count(b"}") >= 1 and len(buf) > 200:
                            break
                except Exception:
                    listen = await listen_task
                    return False, "", False, False, {}, listen, 0.0, "", False
                finally:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass

                sep = buf.find(b"\r\n\r\n")
                if sep == -1:
                    sep = buf.find(b"\n\n")
                if sep == -1:
                    listen = await listen_task
                    return False, "", False, False, {}, listen, 0.0, "", False
                try:
                    data = json.loads(buf[sep:].strip())
                except Exception:
                    listen = await listen_task
                    return False, "", False, False, {}, listen, 0.0, "", False
                country = data.get("country", "")
                country_code = data.get("countryCode", "")
                http_latency = time.monotonic() - t0
                egress = {
                    "egress_ip": data.get("query", ""),
                    "egress_city": data.get("city", ""),
                    "egress_isp": data.get("isp", ""),
                    "egress_country": data.get("country", ""),
                }

            listen = await listen_task
            if self.country_filter and country_code != self.country_filter:
                return False, country, False, False, egress, listen, 0.0, country_code, False
            if self.us_only and country != "United States":
                return False, country, False, False, egress, listen, 0.0, country_code, False

            connect_ok, mitm_suspect = await self._check_proxy_connect(host, port, is_socks)
            supports_connect = connect_ok

            if not connect_ok and not is_socks:
                # HTTP-only proxies cannot tunnel HTTPS, so they are useless for us.
                return False, country, False, mitm_suspect, egress, listen, http_latency, country_code, False

            if not connect_ok:
                return False, country, False, mitm_suspect, egress, listen, http_latency, country_code, False
            return True, country, True, mitm_suspect, egress, listen, http_latency, country_code, False

    async def _check_proxy_connect(self, host: str, port: int, is_socks: bool = False) -> tuple:
            try:
                r, w = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=self.timeout)
            except Exception:
                return False, False
            try:
                if is_socks:
                    if port == 4145:
                        ok = await self._socks4_test(r, w)
                    else:
                        ok = await self._socks5_test(r, w)
                    if ok:
                        mitm = await self._check_mitm_socks(r, w, port)
                        return ok, mitm
                    return ok, False
                else:
                    req = f"CONNECT 2ip.ru:443 HTTP/1.1\r\nHost: 2ip.ru:443\r\n\r\n"
                    w.write(req.encode())
                    await asyncio.wait_for(w.drain(), timeout=self.timeout)
                    try:
                        resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
                        if b"200" not in resp.split(b"\r\n")[0]:
                            return False, False
                    except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                        return False, False

                    mitm = await self._check_mitm_http(r, w)
                    return True, mitm
            except Exception:
                return False, False
            finally:
                try:
                    w.close()
                except Exception:
                    pass

    def _make_ssl_ctx(self):
            if getattr(self, "_ssl_ctx", None) is not None:
                return self._ssl_ctx
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            self._ssl_ctx = ctx
            return ctx

    def _ssl_ctx_verified(self):
            try:
                import ssl as _ssl
                ctx = _ssl.create_default_context()
                ctx.check_hostname = True
                ctx.verify_mode = _ssl.CERT_REQUIRED
                return ctx
            except Exception:
                return self._make_ssl_ctx()

    async def _check_ssl(self, addr: str) -> tuple:
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                return False, "", "", {}, 0.0, False
            ctx = self._make_ssl_ctx()
            t0 = time.monotonic()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port, ssl=ctx, server_hostname=host),
                    timeout=self.timeout,
                )
            except Exception:
                return False, "", "", {}, 0.0, False

            supports_connect = False
            buf = b""
            try:
                req = f"CONNECT ip-api.com:80 HTTP/1.1\r\nHost: ip-api.com:80\r\n\r\n"
                writer.write(req.encode())
                await asyncio.wait_for(writer.drain(), timeout=self.timeout)
                try:
                    resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=self.timeout)
                    status_line = resp.split(b"\r\n")[0]
                    connect_ok = b"200" in status_line
                    if connect_ok:
                        supports_connect = True
                        req = (
                            "GET /json/ HTTP/1.0\r\n"
                            "Host: ip-api.com\r\n"
                            "User-Agent: huntproxy\r\n"
                            "Connection: close\r\n"
                            "\r\n"
                        )
                        writer.write(req.encode())
                        await asyncio.wait_for(writer.drain(), timeout=self.timeout)
                        while True:
                            try:
                                chunk = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
                            except asyncio.TimeoutError:
                                break
                            if not chunk:
                                break
                            buf += chunk
                            if buf.count(b"}") >= 1 and len(buf) > 200:
                                break
                    else:
                        req = (
                            "GET http://ip-api.com/json/ HTTP/1.0\r\n"
                            "Host: ip-api.com\r\n"
                            "User-Agent: huntproxy\r\n"
                            "Connection: close\r\n"
                            "\r\n"
                        )
                        writer.write(req.encode())
                        await asyncio.wait_for(writer.drain(), timeout=self.timeout)
                        while True:
                            try:
                                chunk = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
                            except asyncio.TimeoutError:
                                break
                            if not chunk:
                                break
                            buf += chunk
                            if buf.count(b"}") >= 1 and len(buf) > 200:
                                break
                except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                    req = (
                        "GET http://ip-api.com/json/ HTTP/1.0\r\n"
                        "Host: ip-api.com\r\n"
                        "User-Agent: huntproxy\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    )
                    writer.write(req.encode())
                    await asyncio.wait_for(writer.drain(), timeout=self.timeout)
                    buf = b""
                    while True:
                        try:
                            chunk = await asyncio.wait_for(reader.read(4096), timeout=self.timeout)
                        except asyncio.TimeoutError:
                            break
                        if not chunk:
                            break
                        buf += chunk
                        if buf.count(b"}") >= 1 and len(buf) > 200:
                            break
            except Exception:
                return False, "", "", {}, 0.0, False
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            sep = buf.find(b"\r\n\r\n")
            if sep == -1:
                sep = buf.find(b"\n\n")
            if sep == -1:
                return False, "", "", {}, 0.0, False
            try:
                data = json.loads(buf[sep:].strip())
            except Exception:
                return False, "", "", {}, 0.0, False
            if "country" not in data and "query" not in data:
                return False, "", "", {}, 0.0, False
            ssl_latency = time.monotonic() - t0
            country = data.get("country", "")
            country_code = data.get("countryCode", "")
            egress = {
                "egress_ip": data.get("query", ""),
                "egress_city": data.get("city", ""),
                "egress_isp": data.get("isp", ""),
                "egress_country": data.get("country", ""),
            }
            return True, country, country_code, egress, ssl_latency, supports_connect

    async def _measure_speed(self, host: str, port: int, is_socks: bool = False, use_ssl: bool = False, supports_connect: bool = False) -> float:
            for srv_host, srv_path, expected_size in self.SPEED_SERVERS:
                speed = await self._speed_single(host, port, is_socks, srv_host, srv_path, expected_size, use_ssl, supports_connect)
                if speed > 0:
                    return speed
            return 0.0

    async def _speed_open(self, host: str, port: int, is_socks: bool, use_ssl: bool) -> tuple:
            """Open a fresh connection for a speed measurement attempt."""
            conn_kwargs = {}
            if use_ssl:
                ctx = self._make_ssl_ctx()
                conn_kwargs["ssl"] = ctx
                conn_kwargs["server_hostname"] = host
            r, w = await asyncio.wait_for(
                asyncio.open_connection(host, port, **conn_kwargs), timeout=self.timeout)
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
                while True:
                    try:
                        chunk = await asyncio.wait_for(r.read(65536), timeout=30)
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
                await asyncio.wait_for(w.drain(), timeout=self.timeout)
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
                await asyncio.wait_for(w.drain(), timeout=self.timeout)
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
                while True:
                    try:
                        chunk = await asyncio.wait_for(r.read(65536), timeout=30)
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

    async def _check_mitm_http(self, r, w) -> bool:
            try:
                addr = w.transport.get_extra_info('peername')
                if not addr: return False
                host, port = addr
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-sSf", "--max-time", "10",
                    "-o", "/dev/null", "-w", "%{ssl_verify_result}",
                    "-x", f"http://{host}:{port}",
                    "https://2ip.ru",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode != 0:
                    return True
                verify = stdout.decode().strip()
                return verify != "0"
            except Exception:
                return False

    async def _check_mitm_socks(self, r, w, port: int = 0) -> bool:
            try:
                addr = r._transport.get_extra_info('peername')
                if not addr: return False
                host, _ = addr
                if port in (4145,):
                    proto = "socks4a"
                else:
                    proto = "socks5h"
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-sSf", "--max-time", "10",
                    "-o", "/dev/null", "-w", "%{ssl_verify_result}",
                    "-x", f"{proto}://{host}:{port}",
                    "https://2ip.ru",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode != 0:
                    return True
                verify = stdout.decode().strip()
                return verify != "0"
            except Exception:
                return False

    async def _socks5_test(self, r, w) -> bool:
            try:
                w.write(bytes([5, 1, 0])); await w.drain()
                resp = await asyncio.wait_for(r.readexactly(2), timeout=8)
                if resp[1] != 0: return False
                req = bytes([5, 1, 0, 3, 13]) + b"httpbin.org" + b"\x01\xbb"
                w.write(req); await w.drain()
                hdr = await asyncio.wait_for(r.readexactly(4), timeout=8)
                if hdr[1] != 0: return False
                atyp = hdr[3]
                if atyp == 1:
                    await asyncio.wait_for(r.readexactly(6), timeout=8)
                elif atyp == 3:
                    dl = await asyncio.wait_for(r.readexactly(1), timeout=8)
                    await asyncio.wait_for(r.readexactly(dl[0] + 2), timeout=8)
                elif atyp == 4:
                    await asyncio.wait_for(r.readexactly(18), timeout=8)
                else:
                    return False
                return True
            except Exception:
                return False
                req = bytes([5, 1, 0, 3, 13]) + b"httpbin.org" + b"\x01\xbb"
                w.write(req); await w.drain()
                resp = await asyncio.wait_for(r.readexactly(10), timeout=8)
                return resp[1] == 0
            except Exception:
                return False

    async def _socks4_test(self, r, w) -> bool:
            try:
                req = bytes([4, 1, 0, 80, 0, 0, 0, 1]) + b"\x00" + b"httpbin.org\x00"
                w.write(req); await w.drain()
                resp = await asyncio.wait_for(r.readexactly(8), timeout=8)
                return resp[1] == 0x5A
            except Exception:
                return False

    async def _resolve_geo(self, ip: str) -> dict:
            if ip in self._geo_cache:
                return self._geo_cache[ip]
            try:
                r, w = await asyncio.wait_for(
                    asyncio.open_connection("ip-api.com", 80), timeout=5)
            except Exception:
                return {}
            try:
                req = f"GET /json/{ip} HTTP/1.0\r\nHost: ip-api.com\r\nUser-Agent: huntproxy\r\nConnection: close\r\n\r\n"
                w.write(req.encode())
                await asyncio.wait_for(w.drain(), timeout=5)
                buf = b""
                while True:
                    try:
                        chunk = await asyncio.wait_for(r.read(4096), timeout=5)
                    except asyncio.TimeoutError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    if buf.count(b"}") >= 1 and len(buf) > 200:
                        break
            except Exception:
                return {}
            finally:
                try:
                    w.close()
                except Exception:
                    pass
            sep = buf.find(b"\r\n\r\n")
            if sep == -1:
                sep = buf.find(b"\n\n")
            if sep == -1:
                return {}
            try:
                data = json.loads(buf[sep:].strip())
            except Exception:
                return {}
            result = {
                "country": data.get("country", ""),
                "city": data.get("city", ""),
                "isp": data.get("isp", ""),
            }
            self._geo_cache[ip] = result
            return result

    async def _socks_egress(self, host: str, port: int) -> dict:
            try:
                r, w = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=self.timeout)
            except Exception:
                return {}
            try:
                if port == 4145:
                    req = bytes([4, 1, 0, 80, 0, 0, 0, 1]) + b"\x00" + b"ip-api.com\x00"
                    w.write(req); await asyncio.wait_for(w.drain(), timeout=8)
                    resp = await asyncio.wait_for(r.readexactly(8), timeout=8)
                    if resp[1] != 0x5A:
                        return {}
                else:
                    w.write(bytes([5, 1, 0])); await asyncio.wait_for(w.drain(), timeout=8)
                    resp = await asyncio.wait_for(r.readexactly(2), timeout=8)
                    if resp[1] != 0:
                        return {}
                    req = bytes([5, 1, 0, 3, 9]) + b"ip-api.com" + b"\x00\x50"
                    w.write(req); await asyncio.wait_for(w.drain(), timeout=8)
                    hdr = await asyncio.wait_for(r.readexactly(4), timeout=8)
                    if hdr[1] != 0:
                        return {}
                    atyp = hdr[3]
                    if atyp == 1:
                        await asyncio.wait_for(r.readexactly(6), timeout=8)
                    elif atyp == 3:
                        dl = await asyncio.wait_for(r.readexactly(1), timeout=8)
                        await asyncio.wait_for(r.readexactly(dl[0] + 2), timeout=8)
                    elif atyp == 4:
                        await asyncio.wait_for(r.readexactly(18), timeout=8)
                    else:
                        return {}
                w.write(b"GET /json/ HTTP/1.0\r\nHost: ip-api.com\r\nUser-Agent: huntproxy\r\nConnection: close\r\n\r\n")
                await asyncio.wait_for(w.drain(), timeout=8)
                buf = b""
                while True:
                    try:
                        chunk = await asyncio.wait_for(r.read(4096), timeout=8)
                    except asyncio.TimeoutError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    if buf.count(b"}") >= 1 and len(buf) > 200:
                        break
            except Exception:
                return {}
            finally:
                try:
                    w.close()
                except Exception:
                    pass
            sep = buf.find(b"\r\n\r\n")
            if sep == -1:
                sep = buf.find(b"\n\n")
            if sep == -1:
                return {}
            try:
                data = json.loads(buf[sep:].strip())
            except Exception:
                return {}
            return {
                "egress_ip": data.get("query", ""),
                "egress_city": data.get("city", ""),
                "egress_isp": data.get("isp", ""),
                "egress_country": data.get("country", ""),
            }

    def _record_proxy_check(self, addr: str, ts: float, latency: float,
                                  speed: float, ok: bool):
            try:
                conn = self._stats_db()
                conn.execute(
                    "INSERT INTO proxy_checks (address, ts, latency, speed, ok) VALUES (?,?,?,?,?)",
                    (addr, ts, latency, speed, 1 if ok else 0),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error("record proxy check: %s", e)

    def _update_rating(self, addr: str, ok: bool, country: str, latency: float,
                            supports_connect: bool = False, mitm_suspect: bool = False,
                            egress: dict = None, listen: dict = None,
                            speed: float = 0.0, country_code: str = "",
                            ssl_supported: bool = False):
            r = self.ratings.get(addr)
            if not r:
                r = ProxyRating(
                    address=addr,
                    country=country,
                    country_code=country_code or country_code_from_name(country),
                    first_seen=time.time(),
                    source_ids=list(self._addr_sources.get(addr, [])),
                )
                try:
                    p = int(addr.rsplit(":", 1)[1])
                    if p in (1080, 10808, 9050):
                        r.protocol = "socks5"
                    elif p == 4145:
                        r.protocol = "socks4"
                except ValueError:
                    pass
            was_working = r.checks_ok > 0
            r.checks_total += 1
            r.last_check = time.time()
            r.last_latency = latency
            if ok:
                r.checks_ok += 1
                r.latency_sum += latency
                r.latency_count += 1
                r.last_status = "ok"
                r.last_ok = time.time()
                r.consecutive_fails = 0
                if speed > 0:
                    r.speed_sum += speed
                    r.speed_count += 1
                    r.last_speed = speed
                    r.speed_fails = 0
                else:
                    r.speed_fails += 1
                if country and (not r.country or len(country) > len(r.country)):
                    r.country = country
                if country_code and not r.country_code:
                    r.country_code = country_code
                elif country and not r.country_code:
                    r.country_code = country_code_from_name(country)
                r.supports_connect = supports_connect
                r.ssl_supported = ssl_supported
                if ssl_supported and r.protocol not in ('socks5', 'socks4'):
                    r.protocol = 'https'
                if mitm_suspect:
                    r.mitm_suspect = True
                if egress:
                    r.egress_ip = egress.get("egress_ip") or r.egress_ip
                    r.egress_city = egress.get("egress_city") or r.egress_city
                    r.egress_isp = egress.get("egress_isp") or r.egress_isp
                    r.egress_country = egress.get("egress_country") or r.egress_country
                    if egress.get("egress_country") and not r.egress_country_code:
                        r.egress_country_code = country_code_from_name(egress["egress_country"])
                if listen:
                    r.listen_country = listen.get("country") or r.listen_country
                    if listen.get("country") and not r.listen_country_code:
                        r.listen_country_code = country_code_from_name(listen["country"])
                    r.listen_city = listen.get("city") or r.listen_city
                    r.listen_isp = listen.get("isp") or r.listen_isp
            else:
                r.last_status = "failed"
                r.consecutive_fails += 1
            self.ratings[addr] = r
            if r.egress_ip:
                self._apply_ip_blacklist_to_proxy(addr, r.egress_ip)
            if ok or was_working:
                self._record_proxy_check(addr, r.last_check, latency, speed, ok)
            self._rating_updates_since_save += 1
            if self._rating_updates_since_save >= 25:
                self._save_state()
                self._save_working_file()
                self._rating_updates_since_save = 0
