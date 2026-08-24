"""Full 0-100 fraud/risk score for a proxy's egress IP via proxycheck.io.

ip-api.com (used elsewhere) only returns boolean flags — no continuous
score.  This module queries proxycheck.io (`risk=1`) THROUGH the tested
proxy, so the service sees the egress IP — same architecture as the
ip-api egress probes.  The anonymous free tier quota is per source IP,
and every request here originates from a different egress IP, so each
proxy effectively has its own quota.

Returns {} on any failure: fraud scoring is purely additive and must
never break the check pipeline.
"""

import asyncio
import json

from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect

FRAUD_HOST = "proxycheck.io"
FRAUD_QUERY = "/v2/?risk=1&vpn=1&asn=1"


class FraudScoreMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})

    @staticmethod
    def _parse_fraud_payload(buf: bytes) -> dict:
            """Extract {provider, score?, proxy?, type?} from proxycheck JSON."""
            sep = buf.find(b"\r\n\r\n")
            if sep == -1:
                sep = buf.find(b"\n\n")
            if sep == -1:
                return {}
            try:
                data = json.loads(buf[sep:].strip())
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return {}
            if not isinstance(data, dict) or data.get("status") != "ok":
                return {}
            node = next((v for v in data.values() if isinstance(v, dict)), None)
            if node is None:
                return {}
            out = {"provider": "proxycheck"}
            risk = node.get("risk")
            if isinstance(risk, int) and 0 <= risk <= 100:
                out["score"] = risk
            elif isinstance(risk, float):
                out["score"] = int(round(risk))
            proxy_flag = node.get("proxy")
            if isinstance(proxy_flag, str):
                out["proxy"] = proxy_flag.lower() == "yes"
            ntype = node.get("type")
            if isinstance(ntype, str) and ntype:
                out["type"] = ntype
            return out

    async def _fetch_fraud_score(self, addr: str) -> dict:
            """Query proxycheck.io through the proxy; returns parsed payload."""
            try:
                host, port_str = addr.rsplit(":", 1)
                port = int(port_str)
            except ValueError:
                return {}
            is_socks = port in self._SOCKS_PORTS
            w = None
            try:
                r, w = await self._outbound_connect(host, port,
                                                    timeout=self.effective_timeout)
                proto = "socks4" if port == 4145 else ("socks5" if is_socks else "http")
                tunnel = await self._fraud_tunnel(r, w, proto)
                if not tunnel:
                    return {}
                sw = await self._fraud_start_tls(r, w)
                if sw is None:
                    return {}
                req = (
                    f"GET {FRAUD_QUERY} HTTP/1.0\r\n"
                    f"Host: {FRAUD_HOST}\r\n"
                    "User-Agent: huntproxy\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                )
                sw.write(req.encode())
                await asyncio.wait_for(sw.drain(), timeout=self.effective_timeout)
                buf = await self._fraud_read(sw)
                return self._parse_fraud_payload(buf)
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return {}
            finally:
                try:
                    if w is not None:
                        w.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)

    async def _fraud_tunnel(self, r, w, proto: str) -> bool:
            hs = min(self.effective_timeout + 7, 20)
            try:
                if proto == "socks4":
                    return await socks4_connect(r, w, FRAUD_HOST, 443, handshake_timeout=hs)
                if proto == "socks5":
                    return await socks5_connect(r, w, FRAUD_HOST, 443, handshake_timeout=hs)
                return await http_connect(r, w, FRAUD_HOST, 443)
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return False

    async def _fraud_start_tls(self, r, w):
            """Upgrade the tunnel to verified TLS; returns a new StreamWriter
            sharing the original reader (same pattern as _outbound_connect)."""
            import ssl as _ssl
            try:
                ctx = _ssl.create_default_context()
                loop = asyncio.get_running_loop()
                transport = w.transport
                protocol = transport.get_protocol()
                new_transport = await asyncio.wait_for(
                    loop.start_tls(transport, protocol, ctx,
                                   server_hostname=FRAUD_HOST),
                    timeout=self.effective_timeout + 10,
                )
                return asyncio.StreamWriter(new_transport, protocol, r, loop)
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return None

    @staticmethod
    async def _fraud_read(sw, max_bytes: int = 65536) -> bytes:
            buf = b""
            while len(buf) < max_bytes:
                try:
                    chunk = await asyncio.wait_for(sw.read(4096), timeout=10)
                except asyncio.TimeoutError:
                    break
                if not chunk:
                    break
                buf += chunk
            return buf
