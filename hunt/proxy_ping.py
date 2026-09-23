"""Continuous proxy ping — measures latency through the currently active
client-traffic path once per second and keeps a short sample window for the
UI badge.

Primary source resolution order (what user traffic actually goes through):
  1. active pool proxy (client-traffic proxy, incl. auto-failover picks);
  2. direct connection (tunneled through the channel when one is set — that
     is still the path user traffic takes in direct mode).

The engine's own channel (upstream) proxy is measured in parallel and exposed
separately as ``channel`` so the topbar channel chip can show it without
replacing the end-to-end client-path latency in the main ping badge.

The probe is a plain TCP connect to a canary host:443 through the resolved
source — lightweight, no payload, closes immediately after connect.  Geo
info (country/city/ISP) comes from the pool rating's egress fields or the
canary direct-info cache.
"""

import asyncio
import time

from hunt.constants import logger
from hunt.conn import socks5_connect, socks4_connect, http_connect

PING_HOSTS = ("ya.ru", "google.com", "2ip.ru")
PING_WINDOW = 60
PING_INTERVAL = 1.0
PING_TIMEOUT = 8.0


class ProxyPingMixin:
    def _init_proxy_ping(self):
        self._ping_task = None
        self._ping_samples: list[dict] = []
        self._ping_channel_samples: list[dict] = []
        self._ping_host_idx = 0
        self._ping_last: dict = {
            "ts": 0.0, "ok": False, "latency": -1, "error": "",
            "source": "none", "proxy_addr": "", "host": "",
            "upstream_kind": "none",
        }
        self._ping_channel_last: dict = {
            "ts": 0.0, "ok": False, "latency": -1, "error": "", "addr": "",
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
                if self._channel_is_set():
                    # Two lightweight probes per tick: the end-to-end client
                    # path (badge) and the engine channel (chip).
                    await asyncio.gather(self._ping_once(), self._ping_channel_once())
                else:
                    await self._ping_once()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.debug("suppressed", exc_info=True)
            await asyncio.sleep(PING_INTERVAL)

    # ── source resolution ─────────────────────────────────────────────

    def _ping_source(self) -> dict:
        """Resolve the client-traffic path the main ping goes through.

        Returns a dict with kind in (pool, direct) plus connection parameters
        and geo where already known. The engine channel is deliberately not
        the primary source: the badge must show the end-to-end path user
        traffic takes, with the channel measured separately.
        """
        eff = getattr(self, "_effective_upstream", None) or {}
        addr = eff.get("addr") or getattr(self, "_proxy_active_addr", None) or ""
        upstream_kind = eff.get("kind") or ("select" if addr else "direct")
        if addr and addr in self.ratings:
            r = self.ratings[addr]
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 80
            return {
                "kind": "pool", "upstream_kind": upstream_kind, "addr": addr,
                "protocol": r.protocol or "http", "host": host, "port": port,
                "geo": {
                    "country": r.egress_country or "",
                    "country_code": r.egress_country_code or "",
                    "city": r.egress_city or "",
                    "isp": r.egress_isp or "",
                    "ip": r.egress_ip or "",
                },
            }
        return {"kind": "direct", "upstream_kind": "direct", "addr": "", "geo": {
            "country": getattr(self, "_canary_last_country", ""),
            "country_code": "",
            "city": getattr(self, "_canary_last_city", ""),
            "isp": getattr(self, "_canary_last_isp", ""),
            "ip": getattr(self, "_canary_last_ip", ""),
        }}

    def _ping_channel_source(self) -> dict | None:
        """Resolve the engine channel proxy, or None when no channel is set."""
        route = self._resolve_channel()
        if not route or route == "direct":
            return None
        proxy = self._channel_proxy_cached()
        if proxy is None:
            return None
        return {"addr": f"{proxy['host']}:{proxy['port']}", "route": route}

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
            "upstream_kind": src.get("upstream_kind", src["kind"]),
        }
        self._ping_samples.append(
            {"ts": self._ping_last["ts"], "ok": ok, "latency": latency}
        )
        if len(self._ping_samples) > PING_WINDOW:
            self._ping_samples = self._ping_samples[-PING_WINDOW:]

    async def _ping_channel_once(self):
        """Probe the engine channel proxy (parallel to the main ping)."""
        src = self._ping_channel_source()
        if src is None:
            self._ping_channel_last = {
                "ts": time.time(), "ok": False, "latency": -1,
                "error": "", "addr": "",
            }
            return
        host = PING_HOSTS[self._ping_host_idx % len(PING_HOSTS)]
        t0 = time.monotonic()
        ok, latency, err = False, -1, ""
        try:
            reader, writer = await self._outbound_connect(host, 443, timeout=PING_TIMEOUT)
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
        self._ping_channel_last = {
            "ts": time.time(), "ok": ok, "latency": latency,
            "error": err, "addr": src["addr"],
        }
        self._ping_channel_samples.append(
            {"ts": self._ping_channel_last["ts"], "ok": ok, "latency": latency}
        )
        if len(self._ping_channel_samples) > PING_WINDOW:
            self._ping_channel_samples = self._ping_channel_samples[-PING_WINDOW:]

    def _channel_ping_status(self) -> dict | None:
        if not self._channel_is_set():
            return None
        src = self._ping_channel_source()
        samples = list(self._ping_channel_samples)
        latencies = [s["latency"] for s in samples if s["ok"]]
        return {
            "addr": (src or {}).get("addr", ""),
            "route": (src or {}).get("route", ""),
            "last": dict(self._ping_channel_last),
            "samples": samples,
            "ok_count": sum(1 for s in samples if s["ok"]),
            "total": len(samples),
            "avg": int(sum(latencies) / len(latencies)) if latencies else -1,
        }

    def get_proxy_ping_status(self) -> dict:
        samples = list(self._ping_samples)
        ok_count = sum(1 for s in samples if s["ok"])
        latencies = [s["latency"] for s in samples if s["ok"]]
        last = dict(self._ping_last)
        src = self._ping_source()
        last["geo"] = src["geo"]
        return {
            "running": self._ping_task is not None and not self._ping_task.done(),
            "source": src["kind"],
            "route": src.get("route", ""),
            "proxy_addr": last["proxy_addr"],
            "upstream_kind": last.get("upstream_kind", ""),
            "geo": last["geo"],
            "last": last,
            "samples": samples,
            "ok_count": ok_count,
            "total": len(samples),
            "avg": int(sum(latencies) / len(latencies)) if latencies else -1,
            "interval": PING_INTERVAL,
            "window": PING_WINDOW,
            "channel": self._channel_ping_status(),
        }
