"""Functional split of the huntproxy backend."""

import asyncio
import json
import ssl as _ssl
import time
from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating

class CheckSslMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    async def _check_ssl(self, addr: str) -> tuple:
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                return False, "", "", {}, 0.0, False
            ctx = self._make_ssl_ctx()
            t0 = time.monotonic()
            try:
                reader, writer = await self._outbound_connect(
                    host, port, use_ssl=True, server_hostname=host, timeout=self.effective_timeout)
            except Exception:
                return False, "", "", {}, 0.0, False

            supports_connect = False
            buf = b""
            try:
                req = f"CONNECT ip-api.com:80 HTTP/1.1\r\nHost: ip-api.com:80\r\n\r\n"
                writer.write(req.encode())
                await asyncio.wait_for(writer.drain(), timeout=self.effective_timeout)
                try:
                    resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=self.effective_timeout)
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
                        await asyncio.wait_for(writer.drain(), timeout=self.effective_timeout)
                        while True:
                            try:
                                chunk = await asyncio.wait_for(reader.read(4096), timeout=self.effective_timeout)
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
                        await asyncio.wait_for(writer.drain(), timeout=self.effective_timeout)
                        while True:
                            try:
                                chunk = await asyncio.wait_for(reader.read(4096), timeout=self.effective_timeout)
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
                    await asyncio.wait_for(writer.drain(), timeout=self.effective_timeout)
                    buf = b""
                    while True:
                        try:
                            chunk = await asyncio.wait_for(reader.read(4096), timeout=self.effective_timeout)
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
            if getattr(self, "_ssl_ctx_verified_cache", None) is not None:
                return self._ssl_ctx_verified_cache
            try:
                import ssl as _ssl
                ctx = _ssl.create_default_context()
                ctx.check_hostname = True
                ctx.verify_mode = _ssl.CERT_REQUIRED
                self._ssl_ctx_verified_cache = ctx
                return ctx
            except Exception:
                return self._make_ssl_ctx()

