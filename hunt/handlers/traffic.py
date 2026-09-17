"""Traffic handlers — live traffic, requests/clients, full-text search.

Also owns the in-memory traffic helpers ``_mem_traffic``, ``_route_type`` and
``_aggregate_routes``. Detail (per-client), report (domains/errors/routes/
bandwidth) and dashboard-summary handlers live in sibling mixins.
"""

import asyncio
import json
import time
from urllib.parse import urlparse

from hunt.constants import logger
from hunt.handlers import _int_param, _qs
from hunt.handlers.traffic_common import (
    _DNS_CACHE,
    _SEARCH_CACHE,
    _SEARCH_REFRESHING,
    _SEARCH_TTL,
    _resolve_hostname,
)
from hunt.handlers.traffic_detail import TrafficDetailMixin
from hunt.handlers.traffic_report import TrafficReportMixin
from hunt.handlers.traffic_summary import TrafficSummaryMixin


class TrafficHandlers(TrafficDetailMixin, TrafficReportMixin, TrafficSummaryMixin):
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    def _mem_traffic(self, cutoff: float = 0) -> list:
        """Recent traffic entries from the in-memory proxy log.

        Used as a fallback when the stats DB is unavailable or empty, so the
        Traffic Monitor widgets stay populated even if DB writes failed."""
        try:
            log = list(self.server.proxy.log)
        except Exception:
            return []
        out = []
        for e in log:
            ts = e.get("ts", 0) or 0
            if ts >= cutoff:
                out.append(e)
        return out

    @staticmethod
    def _route_type(up: str) -> str:
        if not up or up == "?" or up == "unknown":
            return "other"
        if up == "direct" or up.startswith("direct"):
            return "direct"
        if up.startswith("proxy:"):
            return "proxy"
        if up.startswith("pool:"):
            return "pool"
        if up.startswith("custom:"):
            return "custom"
        return "other"

    def _aggregate_routes(self, entries: list) -> list:
        """Aggregate raw traffic entries into route-type buckets."""
        routes: dict = {}
        for e in entries:
            up = e.get("upstream") or ""
            if not up or up == "?":
                up = "unknown"
            rtype = self._route_type(up)
            rt = routes.setdefault(rtype, {
                "type": rtype, "requests": 0, "bytes_in": 0, "bytes_out": 0,
                "ok": 0, "_dur_sum": 0.0, "upstreams": {},
            })
            rt["requests"] += 1
            rt["bytes_in"] += int(e.get("bytes_in", 0) or 0)
            rt["bytes_out"] += int(e.get("bytes_out", 0) or 0)
            if (e.get("status") or "") == "ok":
                rt["ok"] += 1
            rt["_dur_sum"] += float(e.get("duration", 0) or 0)
            rt["upstreams"][up] = rt["upstreams"].get(up, 0) + 1
        result = []
        for rt in routes.values():
            cnt = rt["requests"] or 1
            result.append({
                "type": rt["type"],
                "requests": rt["requests"],
                "bytes_in": rt["bytes_in"],
                "bytes_out": rt["bytes_out"],
                "success_rate": round(rt["ok"] / cnt * 100, 1),
                "avg_duration": round(rt["_dur_sum"] / cnt, 3),
                "upstreams": [{"upstream": k, "requests": v}
                              for k, v in sorted(rt["upstreams"].items(),
                                                 key=lambda x: x[1], reverse=True)[:5]],
            })
        result.sort(key=lambda x: x["requests"], reverse=True)
        return result

    async def _handle_traffic_live(self, raw_path, body):
        return json.dumps(self.state.get_live_traffic()), 200, "application/json"

    async def _handle_traffic(self, raw_path, body):
        return json.dumps({"points": self.state.get_history("24h")}), 200, "application/json"

    async def _handle_requests(self, raw_path, body):
        mem = list(self.server.proxy.log)[-50:]
        try:
            conn = self.state._stats_db()
            rows = conn.execute("SELECT ts, client, target, status, upstream, bytes_in, bytes_out, duration, via FROM traffic_log ORDER BY id DESC LIMIT 50").fetchall()
            conn.close()
            db_reqs = [dict(r) for r in rows]
        except Exception:
            db_reqs = []
        reqs = db_reqs if db_reqs else mem
        return json.dumps({"requests": reqs}), 200, "application/json"

    async def _handle_clients(self, raw_path, body):
        # GROUP BY over the full traffic_log — keep it off the event loop.
        return json.dumps(await asyncio.to_thread(self._clients_payload)), 200, "application/json"

    def _clients_payload(self):
        clients = {}
        try:
            conn = self.state._stats_db()
            rows = conn.execute("SELECT client, COUNT(*) as requests, MAX(ts) as last_seen FROM traffic_log GROUP BY client ORDER BY requests DESC LIMIT 20").fetchall()
            conn.close()
            for r in rows:
                clients[r["client"]] = {"client": r["client"], "requests": r["requests"], "last_seen": r["last_seen"]}
        except Exception:
            for entry in self.server.proxy.log:
                c = entry.get("client", "?")
                if c not in clients:
                    clients[c] = {"client": c, "requests": 0, "last_seen": entry.get("ts", 0)}
                clients[c]["requests"] += 1
                clients[c]["last_seen"] = max(clients[c]["last_seen"], entry.get("ts", 0))
        out = sorted(clients.values(), key=lambda x: x["requests"], reverse=True)[:20]
        for c in out:
            c["hostname"] = _resolve_hostname(c["client"])
        return {"clients": out}

    async def _handle_traffic_search(self, raw_path, body):
        """Live filter across the WHOLE traffic_log window — client, DNS-ish
        target, upstream chain (incl. proxy IP), status, ingress type.
        The window follows the period selector on the page (minutes param)."""
        qs = _qs(raw_path)
        q = (qs.get("q") or "").strip().lower()
        minutes = max(1, min(_int_param(qs, "minutes", 1440), 31 * 24 * 60))
        if len(q) < 2:
            return json.dumps({"query": q, "minutes": minutes, "total": 0,
                               "requests": [], "domains": [], "clients": []}), 200, "application/json"
        key = (q, minutes)
        now = time.monotonic()
        cached = _SEARCH_CACHE.get(key)
        if cached is not None:
            if now - cached[0] < _SEARCH_TTL:
                return json.dumps(cached[1]), 200, "application/json"
            # Stale: serve the previous result immediately and refresh in the
            # background (SWR) — a cold re-scan of the window takes seconds.
            if key not in _SEARCH_REFRESHING:
                _SEARCH_REFRESHING.add(key)

                async def _refresh():
                    try:
                        payload = await asyncio.to_thread(self._traffic_search_payload, q, minutes)
                        _SEARCH_CACHE[key] = (time.monotonic(), payload)
                    except Exception:
                        logger.debug("suppressed", exc_info=True)
                    finally:
                        _SEARCH_REFRESHING.discard(key)
                asyncio.create_task(_refresh())
            return json.dumps(cached[1]), 200, "application/json"
        payload = await asyncio.to_thread(self._traffic_search_payload, q, minutes)
        if len(_SEARCH_CACHE) > 200:
            _SEARCH_CACHE.clear()
        _SEARCH_CACHE[key] = (now, payload)
        return json.dumps(payload), 200, "application/json"

    def _traffic_search_payload(self, q: str, minutes: int) -> dict:
        now = time.time()
        cutoff = now - minutes * 60
        cond = ("(instr(lower(client), ?) > 0 OR instr(lower(target), ?) > 0 "
                "OR instr(lower(upstream), ?) > 0 OR instr(lower(status), ?) > 0 "
                "OR instr(lower(via), ?) > 0")
        args = [q, q, q, q, q]
        # Hostnames are not stored in traffic_log; match them via the
        # process-wide DNS cache (populated by /api/clients polling).
        host_matches = [ip for ip, (_, host) in _DNS_CACHE.items()
                        if host and q in host.lower()]
        if host_matches:
            cond += " OR client IN (" + ",".join("?" * len(host_matches)) + ")"
            args.extend(host_matches)
        args = tuple(args)
        cond += ")"
        payload = {"query": q, "minutes": minutes, "total": 0, "requests": [], "domains": [], "clients": []}
        try:
            conn = self.state._stats_db()
            try:
                payload["total"] = int(conn.execute(
                    f"SELECT COUNT(*) AS c FROM traffic_log WHERE ts > ? AND {cond}",  # nosec B608 — cond only static fragments + ? binds
                    (cutoff,) + args).fetchone()["c"])
                rows = [dict(r) for r in conn.execute(
                    f"SELECT ts, client, target, status, upstream, bytes_in, bytes_out, duration, via "  # nosec B608 — static fragments + ? binds
                    f"FROM traffic_log WHERE ts > ? AND {cond} ORDER BY ts DESC LIMIT 50",
                    (cutoff,) + args).fetchall()]
                dom_rows = conn.execute(
                    f"SELECT target, COUNT(*) AS cnt, COALESCE(SUM(bytes_in + bytes_out),0) AS b "  # nosec B608 — static fragments + ? binds
                    f"FROM traffic_log WHERE ts > ? AND {cond} GROUP BY target ORDER BY cnt DESC LIMIT 60",
                    (cutoff,) + args).fetchall()
                cli_rows = conn.execute(
                    f"SELECT client, COUNT(*) AS cnt, MAX(ts) AS last FROM traffic_log "  # nosec B608 — static fragments + ? binds
                    f"WHERE ts > ? AND {cond} GROUP BY client ORDER BY cnt DESC LIMIT 15",
                    (cutoff,) + args).fetchall()
            finally:
                conn.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)
            rows = [e for e in self._mem_traffic(cutoff)
                    if q in json.dumps(e, default=str).lower()]
            dom_rows = []
            cli_rows = []

        domains: dict = {}
        for r in dom_rows:
            target = r["target"] or ""
            try:
                host = urlparse(target if target.startswith("http") else f"http://{target}").hostname or target
            except Exception:
                host = target
            if not host:
                continue
            d = domains.setdefault(host, {"domain": host, "requests": 0, "bytes": 0})
            d["requests"] += int(r["cnt"])
            d["bytes"] += int(r["b"])
        payload["domains"] = sorted(domains.values(), key=lambda d: d["requests"], reverse=True)[:10]

        clients = [{"client": r["client"], "requests": int(r["cnt"]),
                    "last_seen": float(r["last"]), "hostname": _resolve_hostname(r["client"])}
                   for r in cli_rows]
        payload["clients"] = sorted(clients, key=lambda c: c["requests"], reverse=True)[:10]
        payload["requests"] = rows
        return payload
