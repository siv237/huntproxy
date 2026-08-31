"""Continuous proxy ping — measures latency through the currently active
proxy once per second and keeps a short sample window for the UI badge.

Source resolution order (what the ping actually goes through):
  1. channel proxy (engine's own route), if one is selected;
  2. active pool proxy (client-traffic proxy, incl. auto-failover picks);
  3. direct connection.

The probe is a plain TCP connect to a canary host:443 through the resolved
source — lightweight, no payload, closes immediately after connect.  Geo
info (country/city/ISP) comes from the pool rating's egress fields, the
canary direct-info cache, or a lazy ip-api lookup through the channel for
custom channel proxies.
"""

import asyncio
import json
import time

from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect

PING_HOSTS = ("ya.ru", "google.com", "2ip.ru")
PING_WINDOW = 60
PING_INTERVAL = 1.0
PING_TIMEOUT = 8.0
PING_GEO_TTL = 600.0
PING_GEO_RETRY = 60.0


class ProxyPingMixin:
    def _init_proxy_ping(self):
        self._ping_task = None
        self._ping_samples: list[dict] = []
        self._ping_host_idx = 0
        self._ping_geo_cache: dict = {"addr": "", "ts": 0.0, "geo": {}}
        self._ping_geo_fail_ts: float = 0.0
        self._ping_last: dict = {
            "ts": 0.0, "ok": False, "latency": -1, "error": "",
            "source": "none", "proxy_addr": "", "host": "",
        }

    def start_proxy_ping(self):
        """Start the 1s ping loop. Idempotent."""
        if self._ping_task is not None and not self._ping_task.done():
            return
        self._init_proxy_ping()
        self._ping_task = asyncio.create_task(self._proxy_ping_loop())

    def stop_proxy_ping(self):
        if self._ping_task is not None and not self._ping_task.done():
            self._ping_task.cancel()
        self._ping_task = None

    async def _proxy_ping_loop(self):
        while True:
            try:
                await self._ping_once()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.debug("suppressed", exc_info=True)
            await asyncio.sleep(PING_INTERVAL)

    # ── source resolution ─────────────────────────────────────────────

    def _ping_source(self) -> dict:
        """Resolve what the ping currently goes through.

        Returns a dict with kind in (channel, pool, direct) plus connection
        parameters and geo where already known.
        """
        route = self._resolve_channel()
        if route and route != "direct":
            proxy = self._channel_proxy_cached()
            if proxy is not None:
                addr = f"{proxy['host']}:{proxy['port']}"
                geo = {}
                if route.startswith("proxy:"):
                    r = self.ratings.get(route[6:])
                    if r is not None:
                        geo = {
                            "country": r.egress_country or "",
                            "country_code": r.egress_country_code or "",
                            "city": r.egress_city or "",
                            "isp": r.egress_isp or "",
                            "ip": r.egress_ip or "",
                        }
                return {"kind": "channel", "addr": addr, "route": route,
                        "geo": geo, "proxy": proxy}
        addr = getattr(self, "_proxy_active_addr", None) or ""
        if addr and addr in self.ratings:
            r = self.ratings[addr]
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 80
            return {
                "kind": "pool", "addr": addr,
                "protocol": r.protocol or "http", "host": host, "port": port,
                "geo": {
                    "country": r.egress_country or "",
                    "country_code": r.egress_country_code or "",
                    "city": r.egress_city or "",
                    "isp": r.egress_isp or "",
                    "ip": r.egress_ip or "",
                },
            }
        return {"kind": "direct", "addr": "", "geo": {
            "country": getattr(self, "_canary_last_country", ""),
            "country_code": "",
            "city": getattr(self, "_canary_last_city", ""),
            "isp": getattr(self, "_canary_last_isp", ""),
            "ip": getattr(self, "_canary_last_ip", ""),
        }}

    async def _ping_probe(self, src: dict, host: str, port: int):
        """Open a connection to (host, port) through the resolved source."""
        if src["kind"] == "pool":
            proxy = src
            conn_kwargs = {}
            if proxy.get("protocol") == "https":
                ctx = self._make_ssl_ctx()
                conn_kwargs = {"ssl": ctx, "server_hostname": proxy["host"]}
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(proxy["host"], proxy["port"], **conn_kwargs),
                timeout=PING_TIMEOUT,
            )
            proto = proxy.get("protocol", "http")
            if proto == "socks5":
                ok = await socks5_connect(reader, writer, host, port)
            elif proto == "socks4":
                ok = await socks4_connect(reader, writer, host, port)
            else:
                ok = await http_connect(reader, writer, host, port)
            if not ok:
                try:
                    writer.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)
                raise OSError("pool proxy handshake failed")
            return reader, writer
        # channel (handles auth/https) or direct
        return await self._outbound_connect(host, port, timeout=PING_TIMEOUT)

    async def _ping_once(self):
        src = self._ping_source()
        host = PING_HOSTS[self._ping_host_idx % len(PING_HOSTS)]
        t0 = time.monotonic()
        ok, latency, err = False, -1, ""
        try:
            reader, writer = await self._ping_probe(src, host, 443)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                logger.debug("suppressed", exc_info=True)
            latency = int((time.monotonic() - t0) * 1000)
            ok = True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            err = str(e)[:160]
            if not ok:
                self._ping_host_idx += 1
        self._ping_last = {
            "ts": time.time(), "ok": ok, "latency": latency, "error": err,
            "source": src["kind"], "proxy_addr": src["addr"], "host": host,
        }
        self._ping_samples.append(
            {"ts": self._ping_last["ts"], "ok": ok, "latency": latency}
        )
        if len(self._ping_samples) > PING_WINDOW:
            self._ping_samples = self._ping_samples[-PING_WINDOW:]

    def get_proxy_ping_status(self) -> dict:
        samples = list(self._ping_samples)
        ok_count = sum(1 for s in samples if s["ok"])
        latencies = [s["latency"] for s in samples if s["ok"]]
        last = dict(self._ping_last)
        src = self._ping_source()
        last["geo"] = src["geo"]
        if src["kind"] == "channel" and not src["geo"]:
            last["geo"] = self._ping_geo_cached(src["addr"])
        return {
            "running": self._ping_task is not None and not self._ping_task.done(),
            "source": src["kind"],
            "route": src.get("route", ""),
            "proxy_addr": last["proxy_addr"],
            "geo": last["geo"],
            "last": last,
            "samples": samples,
            "ok_count": ok_count,
            "total": len(samples),
            "avg": int(sum(latencies) / len(latencies)) if latencies else -1,
            "interval": PING_INTERVAL,
            "window": PING_WINDOW,
        }

    # ── lazy geo for custom channel proxies ────────────────────────────

    def _ping_geo_cached(self, addr: str) -> dict:
        cache = self._ping_geo_cache
        now = time.time()
        if cache["addr"] == addr and now - cache["ts"] < PING_GEO_TTL:
            return cache["geo"]
        if cache["addr"] != addr and now - self._ping_geo_fail_ts < PING_GEO_RETRY:
            return {}
        # Re-query in the background so the badge is not blocked.
        if cache["addr"] != addr and now - self._ping_geo_fail_ts >= PING_GEO_RETRY:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._ping_fetch_geo(addr))
            except Exception:
                logger.debug("suppressed", exc_info=True)
        return {}

    async def _ping_fetch_geo(self, addr: str):
        try:
            reader, writer = await self._outbound_connect("ip-api.com", 80, timeout=PING_TIMEOUT)
            req = (b"GET /json/?fields=query,country,countryCode,city,isp HTTP/1.1\r\n"
                   b"Host: ip-api.com\r\nConnection: close\r\n\r\n")
            writer.write(req)
            await writer.drain()
            resp = b""
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=5)
                if not chunk:
                    break
                resp += chunk
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                logger.debug("suppressed", exc_info=True)
            body = resp.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in resp else resp
            data = json.loads(body)
            self._ping_geo_cache = {"addr": addr, "ts": time.time(), "geo": {
                "country": data.get("country", ""),
                "country_code": data.get("countryCode", ""),
                "city": data.get("city", ""),
                "isp": data.get("isp", ""),
                "ip": data.get("query", ""),
            }}
        except Exception:
            self._ping_geo_fail_ts = time.time()
            logger.debug("suppressed", exc_info=True)
