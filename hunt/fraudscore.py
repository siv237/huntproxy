"""Full 0-100 fraud/risk score for a proxy's egress IP via proxycheck.io.

ip-api.com (used elsewhere) only returns boolean flags — no continuous
score.  This module queries proxycheck.io (`risk=1`) THROUGH the tested
proxy for a known egress IP.  The anonymous free tier quota is per
source IP, and every request here originates from a different egress
IP, so each proxy effectively has its own quota.

The API requires the target IP in the path (`/v2/<ip>`); callers pass
the egress IP discovered by earlier probes, and when it is unknown this
module resolves it first via ip-api through the same tunnel.

Two transports are attempted in order, each on its own connection:
CONNECT + TLS (trusted), then a plain forward GET — many free proxies
refuse CONNECT to arbitrary hosts but happily relay plain HTTP.
Returns {} on any failure: fraud scoring is purely additive and must
never break the check pipeline.
"""

import asyncio
import json

from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect

FRAUD_HOST = "proxycheck.io"
FRAUD_QUERY = "/v2/{ip}?risk=1&vpn=1&asn=1"


class FraudScoreMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})

    @staticmethod
    def _parse_fraud_payload(buf: bytes) -> dict:
            """Extract {provider, score?, proxy?, type?} from proxycheck JSON."""
            start = buf.find(b"{")
            end = buf.rfind(b"}")
            if start == -1 or end <= start:
                return {}
            try:
                data = json.loads(buf[start:end + 1])
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

    async def _fetch_fraud_score(self, addr: str, egress_ip: str = "") -> dict:
            """Query proxycheck.io through the proxy; returns parsed payload."""
            try:
                host, port_str = addr.rsplit(":", 1)
                port = int(port_str)
            except ValueError:
                return {}
            proto = ("socks4" if port == 4145 else
                     "socks5" if port in self._SOCKS_PORTS else "http")
            try:
                target = egress_ip
                if not target:
                    async with self._fraud_conn(host, port) as conn:
                        target = await self._resolve_egress_ip(conn, proto)
                    if not target:
                        return {}
                buf = b""
                async with self._fraud_conn(host, port) as conn:
                    buf = await self._fraud_https_get(conn, proto,
                                                      FRAUD_QUERY.format(ip=target))
                if not buf:
                    async with self._fraud_conn(host, port) as conn:
                        buf = await self._fraud_plain_request(
                            conn, proto, FRAUD_HOST,
                            FRAUD_QUERY.format(ip=target))
                if not buf:
                    return {}
                return self._parse_fraud_payload(buf)
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return {}

    def _fraud_conn(self, host: str, port: int):
            """Async context manager yielding a fresh (reader, writer) tunnel."""
            class _Conn:
                def __init__(self, owner):
                    self._owner = owner
                    self.pair = None

                async def __aenter__(self):
                    return await self._owner._outbound_connect(
                        host, port, timeout=self._owner.effective_timeout)

                async def __aexit__(self, *exc):
                    if self.pair:
                        try:
                            self.pair[1].close()
                        except Exception:
                            logger.debug("suppressed", exc_info=True)
                    return False

            return _Conn(self)

    async def _resolve_egress_ip(self, conn, proto: str) -> str:
            """Discover the egress IP via plain ip-api query through the proxy."""
            try:
                body = await self._fraud_plain_request(
                    conn, proto, "ip-api.com", "/json/?fields=query")
                start = body.find(b"{")
                end = body.rfind(b"}")
                if start == -1 or end <= start:
                    return ""
                data = json.loads(body[start:end + 1])
                ip = data.get("query") if isinstance(data, dict) else None
                return ip if isinstance(ip, str) and ip else ""
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return ""

    async def _fraud_https_get(self, conn, proto: str, path: str) -> bytes:
            """CONNECT + TLS + GET; reads from the original reader (the TLS
            protocol feeds decrypted bytes into it after start_tls)."""
            r, w = conn
            try:
                if not await self._fraud_tunnel(r, w, proto):
                    return b""
                sw = await self._fraud_start_tls(r, w)
                if sw is None:
                    return b""
                req = (
                    f"GET {path} HTTP/1.0\r\n"
                    f"Host: {FRAUD_HOST}\r\n"
                    "User-Agent: huntproxy\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                )
                sw.write(req.encode())
                await asyncio.wait_for(sw.drain(), timeout=self.effective_timeout)
                return await self._fraud_read(r)
            except Exception:
                logger.debug("suppressed", exc_info=True)
                return b""

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

    async def _fraud_plain_request(self, conn, proto: str, host: str,
                                   path: str) -> bytes:
            """Forward absolute-URI GET through the proxy (no CONNECT)."""
            r, w = conn
            req = (
                f"GET http://{host}{path} HTTP/1.0\r\n"
                f"Host: {host}\r\n"
                "User-Agent: huntproxy\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            if proto in ("socks4", "socks5"):
                connect_fn = socks4_connect if proto == "socks4" else socks5_connect
                hs = min(self.effective_timeout + 7, 20)
                ok = await connect_fn(r, w, host, 80, handshake_timeout=hs)
                if not ok:
                    return b""
            w.write(req.encode())
            await asyncio.wait_for(w.drain(), timeout=self.effective_timeout)
            return await self._fraud_read(r)

    @staticmethod
    async def _fraud_read(reader, max_bytes: int = 65536) -> bytes:
            buf = b""
            while len(buf) < max_bytes:
                try:
                    chunk = await asyncio.wait_for(reader.read(4096), timeout=10)
                except asyncio.TimeoutError:
                    break
                if not chunk:
                    break
                buf += chunk
            return buf
