"""Functional split of the huntproxy backend."""

import asyncio
import json
import ssl as _ssl
import time
from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect
from hunt.geo import country_code_from_name
from hunt.models import ProxyRating

class CheckProxyMixin:
    _SOCKS_PORTS = frozenset({1080, 10808, 9050, 4145})
    async def _check_proxy(self, addr: str) -> tuple:
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                return False, "", False, False, {}, {}, 0.0, "", False
            is_socks = port in (1080, 10808, 9050, 4145)

            t0 = time.monotonic()
            try:
                reader, writer = await self._outbound_connect(host, port, timeout=self.effective_timeout)
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
                r, w = await self._outbound_connect(host, port, timeout=self.effective_timeout)
            except Exception:
                return False, False
            try:
                if is_socks:
                    if port == 4145:
                        ok = await self._socks4_test(r, w)
                    else:
                        ok = await self._socks5_test(r, w)
                    if ok:
                        if self._resolve_channel():
                            # Reuse the existing tunnel to the tested proxy:
                            # build a SOCKS tunnel to 2ip.ru:443 on r,w, then
                            # verify the cert. Avoids a second connection.
                            mitm = await self._check_mitm_socks_via_channel(r, w, port)
                        else:
                            mitm = await self._check_mitm_socks(r, w, port)
                        return ok, mitm
                    return ok, False
                else:
                    req = f"CONNECT 2ip.ru:443 HTTP/1.1\r\nHost: 2ip.ru:443\r\n\r\n"
                    w.write(req.encode())
                    await asyncio.wait_for(w.drain(), timeout=self.effective_timeout)
                    try:
                        resp = await asyncio.wait_for(r.readuntil(b"\r\n\r\n"), timeout=15)
                        if b"200" not in resp.split(b"\r\n")[0]:
                            return False, False
                    except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                        return False, False

                    if self._resolve_channel():
                        mitm = await self._check_mitm_tls_over(w)
                        if mitm and not await self._channel_tls_baseline_trusted():
                            mitm = False
                    else:
                        mitm = await self._check_mitm_http(r, w)
                    return True, mitm
            except Exception:
                return False, False
            finally:
                try:
                    w.close()
                except Exception:
                    pass


    @staticmethod
    def _is_socks_addr(addr: str) -> bool:
            try:
                _, port_str = addr.rsplit(":", 1)
                return int(port_str) in CheckProxyMixin._SOCKS_PORTS
            except Exception:
                return False

