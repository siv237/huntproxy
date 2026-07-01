"""Functional split of the huntproxy backend."""

import asyncio
import ssl as _ssl
from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect

class CheckMitmMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
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


    async def _check_mitm_tls_over(self, w) -> bool:
            """MITM check over an already-established CONNECT tunnel to 2ip.ru:443.

            Used when a channel proxy is active (curl cannot chain channel→tested
            proxy). Upgrades the tunnel to TLS with certificate verification: a
            verification failure means the tested proxy is injecting a fake cert.
            """
            try:
                ctx = self._ssl_ctx_verified()
                loop = asyncio.get_running_loop()
                transport = w.transport
                protocol = transport.get_protocol()
                await loop.start_tls(transport, protocol, ctx, server_hostname="2ip.ru")
                return False
            except _ssl.SSLCertVerificationError:
                return True
            except Exception:
                return False


    async def _check_mitm_socks_via_channel(self, r, w, port: int) -> bool:
            """MITM check reusing the existing channel→tested-proxy SOCKS tunnel.

            Builds a SOCKS4a/SOCKS5 tunnel to 2ip.ru:443 on the already-open
            (r, w), then verifies the TLS certificate. If the channel itself
            intercepts TLS (corporate proxy), the baseline check suppresses the
            false positive.
            """
            try:
                if port == 4145:
                    ok = await socks4_connect(r, w, "2ip.ru", 443)
                else:
                    ok = await socks5_connect(r, w, "2ip.ru", 443)
                if not ok:
                    return False
                mitm = await self._check_mitm_tls_over(w)
                if mitm and not await self._channel_tls_baseline_trusted():
                    # The channel itself intercepts TLS — not the tested proxy.
                    return False
                return mitm
            except Exception:
                return False


    async def _channel_tls_baseline_trusted(self) -> bool:
            """One-time probe: can the channel reach 2ip.ru:443 with a valid cert?

            Cached on the instance (reset by set_channel). When False, the
            channel itself intercepts TLS, so per-proxy MITM verdicts are not
            meaningful and are suppressed.
            """
            cached = getattr(self, "_channel_tls_trusted", None)
            if cached is not None:
                return cached
            if not self._channel_is_set():
                self._channel_tls_trusted = True
                return True
            w = None
            try:
                # Tunnel directly to 2ip.ru:443 via the channel (no tested proxy).
                r, w = await self._outbound_connect("2ip.ru", 443, use_ssl=True,
                                                    server_hostname="2ip.ru",
                                                    timeout=self.effective_timeout)
                # If start_tls inside _outbound_connect succeeded with a verified
                # context, the channel does not intercept. _outbound_connect uses
                # the non-verifying _make_ssl_ctx, so verify explicitly here.
                ctx = self._ssl_ctx_verified()
                loop = asyncio.get_running_loop()
                transport = w.transport
                protocol = transport.get_protocol()
                await loop.start_tls(transport, protocol, ctx, server_hostname="2ip.ru")
                self._channel_tls_trusted = True
                return True
            except _ssl.SSLCertVerificationError:
                self._channel_tls_trusted = False
                self._emit("Channel proxy intercepts TLS — per-proxy MITM checks suppressed", "warn")
                return False
            except Exception:
                # Can't determine — assume trusted to avoid mass false positives.
                self._channel_tls_trusted = True
                return True
            finally:
                try:
                    if w is not None:
                        w.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)


    async def _check_mitm_tls(self, host: str, port: int, is_socks: bool = False) -> bool:
            """MITM check via a fresh tunneled connection (legacy fallback path).

            Opens channel→tested proxy, builds a tunnel to 2ip.ru:443, then
            verifies the TLS certificate. Prefer _check_mitm_socks_via_channel
            which reuses the existing connection.
            """
            w = None
            try:
                r, w = await self._outbound_connect(host, port, timeout=self.effective_timeout)
                if port == 4145:
                    ok = await socks4_connect(r, w, "2ip.ru", 443)
                elif is_socks:
                    ok = await socks5_connect(r, w, "2ip.ru", 443)
                else:
                    ok = await http_connect(r, w, "2ip.ru", 443)
                if not ok:
                    return False
                mitm = await self._check_mitm_tls_over(w)
                if mitm and not await self._channel_tls_baseline_trusted():
                    return False
                return mitm
            except Exception:
                return False
            finally:
                try:
                    if w is not None:
                        w.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)


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

