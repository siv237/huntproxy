"""Functional split of the huntproxy backend."""

import asyncio
import json
from hunt.constants import logger

class CheckGeoMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    async def _resolve_geo(self, ip: str) -> dict:
            if ip in self._geo_cache:
                return self._geo_cache[ip]
            try:
                r, w = await self._outbound_connect("ip-api.com", 80, timeout=5)
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
                    logger.debug("suppressed", exc_info=True)
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
                "country_code": data.get("countryCode", ""),
                "city": data.get("city", ""),
                "isp": data.get("isp", ""),
                "hosting": bool(data.get("hosting")),
                "proxy": bool(data.get("proxy")),
                "mobile": bool(data.get("mobile")),
            }
            self._geo_cache[ip] = result
            return result


    async def _authoritative_egress(self, reported_ip: str, reported_cc: str):
        """Verify a proxy's self-reported egress against a direct ip-api lookup.

        A proxy that returns a forged ip-api response (the "geo-spoofing"
        attack) claims a country/flags that its real egress IP does not have.
        We resolve the reported egress IP directly (outside the proxy) and
        reject the proxy when the direct country code contradicts what the
        proxy reported. Returns (ok, country, country_code, flags) where
        ok=False means the proxy misrepresents its egress and must not reach
        the rating. flags carries the authoritative hosting/proxy/mobile bits
        for fraud scoring. Fail-open when the direct lookup yields nothing
        (transient ip-api outage must not evict a genuine proxy).
        """
        direct = await self._resolve_geo(reported_ip) if reported_ip else {}
        cc = direct.get("country_code", "")
        if cc and reported_cc and cc != reported_cc:
            return False, "", "", {}
        return True, direct.get("country", ""), cc, {
            "hosting": bool(direct.get("hosting")),
            "proxy": bool(direct.get("proxy")),
            "mobile": bool(direct.get("mobile")),
        }

    async def _socks_egress(self, host: str, port: int) -> dict:
            try:
                r, w = await self._outbound_connect(host, port, timeout=self.effective_timeout)
            except Exception:
                return {}
            try:
                if port == 4145:
                    if not await self._socks4_egress_handshake(w, r):
                        return {}
                else:
                    if not await self._socks5_egress_handshake(w, r):
                        return {}
                buf = await self._egress_http_get(w, r)
            except Exception:
                return {}
            finally:
                try:
                    w.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)
            return self._parse_egress_response(buf)

    async def _socks4_egress_handshake(self, w, r) -> bool:
        req = bytes([4, 1, 0, 80, 0, 0, 0, 1]) + b"\x00" + b"ip-api.com\x00"
        w.write(req); await asyncio.wait_for(w.drain(), timeout=8)
        resp = await asyncio.wait_for(r.readexactly(8), timeout=8)
        return resp[1] == 0x5A

    async def _socks5_egress_handshake(self, w, r) -> bool:
        w.write(bytes([5, 1, 0])); await asyncio.wait_for(w.drain(), timeout=8)
        resp = await asyncio.wait_for(r.readexactly(2), timeout=8)
        if resp[1] != 0:
            return False
        req = bytes([5, 1, 0, 3, 9]) + b"ip-api.com" + b"\x00\x50"
        w.write(req); await asyncio.wait_for(w.drain(), timeout=8)
        hdr = await asyncio.wait_for(r.readexactly(4), timeout=8)
        if hdr[1] != 0:
            return False
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

    async def _egress_http_get(self, w, r) -> bytes:
        w.write(b"GET /json/?fields=query,city,isp,country,hosting,proxy,mobile HTTP/1.0\r\nHost: ip-api.com\r\nUser-Agent: huntproxy\r\nConnection: close\r\n\r\n")
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
        return buf

    def _parse_egress_response(self, buf: bytes) -> dict:
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
            "egress_hosting": bool(data.get("hosting")),
            "egress_proxy": bool(data.get("proxy")),
            "egress_mobile": bool(data.get("mobile")),
        }

