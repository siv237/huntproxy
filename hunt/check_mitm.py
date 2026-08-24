"""Multi-target MITM detection via certificate verification over tunnels.

Instead of fetching a page through the proxy with curl (which conflated
slow channels, anti-bot pages, outages and domain blocking with actual
certificate substitution), we build a CONNECT/SOCKS tunnel to a well-known
HTTPS host and upgrade it with a verified TLS handshake — no HTTP request,
no external process, minimal round-trips on slow channels.

A proxy is flagged as MITM only when every successfully reached target
presents an untrusted certificate AND at least two independent targets
were reached. Single-target failures stay inconclusive: DPI filters forge
certificates for specific blocked domains, which is routing censorship,
not a property of the proxy.
"""

import asyncio
import ssl as _ssl
from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect

MITM_TEST_HOSTS = ("www.google.com", "www.wikipedia.org", "ya.ru")


class CheckMitmMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})

    def _mitm_hosts(self) -> list:
            hosts = getattr(self, "mitm_hosts", None)
            return [h for h in (hosts or MITM_TEST_HOSTS) if h]

    @staticmethod
    def _mitm_proto(port: int, is_socks: bool) -> str:
            if is_socks:
                return "socks4" if port == 4145 else "socks5"
            return "http"

    async def _check_mitm_tls_over(self, w, server_hostname: str) -> str | None:
            """Upgrade an established tunnel to TLS with cert verification.

            Returns "clean" (trusted handshake), "mitm" (untrusted or
            mismatched certificate) or None (tunnel died mid-handshake:
            timeout/reset/protocol error — inconclusive, never counts as
            MITM by itself).
            """
            try:
                ctx = self._ssl_ctx_verified()
                loop = asyncio.get_running_loop()
                transport = w.transport
                protocol = transport.get_protocol()
                await asyncio.wait_for(
                    loop.start_tls(transport, protocol, ctx,
                                   server_hostname=server_hostname),
                    timeout=self.effective_timeout + 10,
                )
                return "clean"
            except _ssl.SSLCertVerificationError:
                return "mitm"
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return None

    @staticmethod
    async def _flush_tunnel_noise(r) -> None:
            """Drop leftover bytes from a failed attempt before retrying."""
            try:
                while True:
                    chunk = await asyncio.wait_for(r.read(4096), timeout=0.05)
                    if not chunk:
                        break
            except Exception:
                logger.debug("suppressed", exc_info=True)

    async def _tunnel_to(self, r, w, host: str, proto: str) -> bool:
            """Open a tunnel to host:443 over the open proxy connection."""
            try:
                hs_timeout = min(self.effective_timeout + 7, 20)
                if proto == "socks4":
                    return await socks4_connect(r, w, host, 443,
                                                handshake_timeout=hs_timeout)
                if proto == "socks5":
                    return await socks5_connect(r, w, host, 443,
                                                handshake_timeout=hs_timeout)
                return await http_connect(r, w, host, 443)
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return False

    async def _check_mitm_via(self, r, w, port: int, is_socks: bool) -> tuple:
            """Multi-target MITM probe over one open connection to the proxy.

            Returns (connect_ok, mitm_suspect). connect_ok means at least one
            tunnel succeeded (the proxy forwards traffic at all). mitm_suspect
            requires every reached target to fail certificate verification
            with >=2 targets reached, so one flaky/blocked target alone can
            never flag a proxy.
            """
            proto = self._mitm_proto(port, is_socks)
            reached = bad = 0
            for i, host in enumerate(self._mitm_hosts()):
                if i:
                    await self._flush_tunnel_noise(r)
                if not await self._tunnel_to(r, w, host, proto):
                    continue
                reached += 1
                verdict = await self._check_mitm_tls_over(w, host)
                if verdict == "clean":
                    return True, False
                if verdict == "mitm":
                    bad += 1
            if reached >= 2 and bad == reached:
                if await self._channel_tls_baseline_trusted():
                    return True, True
                return True, False
            return reached > 0, False

    async def _check_mitm_socks_via_channel(self, r, w, port: int) -> tuple:
            """Compat wrapper: MITM probe on an open SOCKS connection."""
            return await self._check_mitm_via(r, w, port, is_socks=True)

    async def _channel_tls_baseline_trusted(self) -> bool:
            """One-time probe: does the channel itself intercept TLS?

            Cached on the instance (reset by set_channel). When False the
            channel presents untrusted certificates regardless of the tested
            proxy, so per-proxy MITM verdicts are suppressed.
            """
            cached = getattr(self, "_channel_tls_trusted", None)
            if cached is not None:
                return cached
            if not self._channel_is_set():
                self._channel_tls_trusted = True
                return True
            for host in self._mitm_hosts():
                w = None
                try:
                    _, w = await self._outbound_connect(
                        host, 443, timeout=self.effective_timeout)
                    verdict = await self._check_mitm_tls_over(w, host)
                except Exception:
                    logger.debug("suppressed", exc_info=True)
                    verdict = None
                finally:
                    try:
                        if w is not None:
                            w.close()
                    except Exception:
                        logger.debug("suppressed", exc_info=True)
                if verdict == "clean":
                    self._channel_tls_trusted = True
                    return True
                if verdict == "mitm":
                    self._channel_tls_trusted = False
                    self._emit("Channel proxy intercepts TLS — per-proxy MITM checks suppressed", "warn")
                    return False
            self._channel_tls_trusted = True
            return True
