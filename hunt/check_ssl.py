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
                buf = await self._ssl_request(reader, writer)
                if buf is None:
                    return False, "", "", {}, 0.0, False
                supports_connect = buf.startswith(b"CONNECT_OK")
                if supports_connect:
                    buf = buf[len(b"CONNECT_OK"):]
            except Exception:
                return False, "", "", {}, 0.0, False
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

            data = self._parse_ssl_response(buf)
            if data is None:
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

    async def _ssl_request(self, reader, writer) -> bytes:
        """Try CONNECT then fallback to plain GET. Returns response bytes."""
        try:
            buf = await self._ssl_connect_request(reader, writer)
            if buf is not None:
                return b"CONNECT_OK" + buf
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            pass
        return await self._ssl_get_request(reader, writer)

    async def _ssl_connect_request(self, reader, writer) -> bytes:
        req = f"CONNECT ip-api.com:80 HTTP/1.1\r\nHost: ip-api.com:80\r\n\r\n"
        writer.write(req.encode())
        await asyncio.wait_for(writer.drain(), timeout=self.effective_timeout)
        resp = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=self.effective_timeout)
        if b"200" not in resp.split(b"\r\n")[0]:
            raise asyncio.IncompleteReadError(b"", None)
        req = (
            "GET /json/ HTTP/1.0\r\n"
            "Host: ip-api.com\r\n"
            "User-Agent: huntproxy\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        writer.write(req.encode())
        await asyncio.wait_for(writer.drain(), timeout=self.effective_timeout)
        return await self._ssl_read_body(reader)

    async def _ssl_get_request(self, reader, writer) -> bytes:
        req = (
            "GET http://ip-api.com/json/ HTTP/1.0\r\n"
            "Host: ip-api.com\r\n"
            "User-Agent: huntproxy\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        writer.write(req.encode())
        await asyncio.wait_for(writer.drain(), timeout=self.effective_timeout)
        return await self._ssl_read_body(reader)

    async def _ssl_read_body(self, reader) -> bytes:
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
        return buf

    def _parse_ssl_response(self, buf: bytes):
        sep = buf.find(b"\r\n\r\n")
        if sep == -1:
            sep = buf.find(b"\n\n")
        if sep == -1:
            return None
        try:
            data = json.loads(buf[sep:].strip())
        except Exception:
            return None
        if "country" not in data and "query" not in data:
            return None
        return data


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

