"""Per-client traffic detail handlers — extracted from handlers/traffic.py."""

import asyncio
import json
import time
from urllib.parse import unquote, urlparse

from hunt.constants import logger
from hunt.handlers import _int_param, _qs
from hunt.handlers.traffic_common import _resolve_hostname


class TrafficDetailMixin:
    async def _handle_client_detail(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        client = unquote(path[len("/api/clients/"):])
        if not client:
            return json.dumps({"error": "client required"}), 400, "application/json"
        hours = _int_param(_qs(raw_path), "hours", 24)
        hours = max(1, min(hours, 24 * 30))
        payload = await asyncio.to_thread(self._client_detail_payload, client, hours)
        return json.dumps(payload), 200, "application/json"

    def _client_detail_payload(self, client: str, hours: int) -> dict:
        """Per-client dashboard: summary, hourly activity, routes, domains, recent.

        Aggregates are computed in SQL over the ts-indexed window so the
        numbers stay exact for clients with millions of rows; the in-memory
        proxy log is the fallback when the stats DB is unavailable. The
        hourly chart always covers the last 24h — per-hour resolution is
        meaningless beyond that."""
        now = time.time()
        cutoff = now - hours * 3600
        try:
            conn = self.state._stats_db()
            try:
                return self._client_detail_sql(conn, client, cutoff, now, hours)
            finally:
                conn.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)
        return self._client_detail_mem(client, cutoff, now, hours)

    def _client_detail_sql(self, conn, client: str, cutoff: float, now: float, hours: int) -> dict:
        row = conn.execute(
            "SELECT COUNT(*) AS c, COALESCE(SUM(bytes_in),0) AS bin, COALESCE(SUM(bytes_out),0) AS bout, "
            "COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END),0) AS okc, "
            "COALESCE(AVG(duration),0) AS avgdur, COALESCE(MIN(ts),0) AS first, COALESCE(MAX(ts),0) AS last "
            "FROM traffic_log WHERE client = ? AND ts > ?",
            (client, cutoff)
        ).fetchone()
        requests = int(row["c"])
        summary = {
            "client": client, "hours": hours, "requests": requests,
            "bytes_in": int(row["bin"]), "bytes_out": int(row["bout"]),
            "ok": int(row["okc"]), "failed": requests - int(row["okc"]),
            "success_rate": round(int(row["okc"]) / requests * 100, 1) if requests else 0.0,
            "avg_duration": round(float(row["avgdur"]), 3),
            "first_seen": float(row["first"]), "last_seen": float(row["last"]),
        }
        summary["total_bytes"] = summary["bytes_in"] + summary["bytes_out"]
        summary["hostname"] = _resolve_hostname(client)

        routes: dict = {}
        for r in conn.execute(
            "SELECT upstream, COUNT(*) AS cnt, COALESCE(SUM(bytes_in + bytes_out),0) AS b "
            "FROM traffic_log WHERE client = ? AND ts > ? GROUP BY upstream",
            (client, cutoff)
        ).fetchall():
            up = r["upstream"] or ""
            if not up or up == "?":
                up = "unknown"
            rtype = self._route_type(up)
            rt = routes.setdefault(rtype, {"type": rtype, "requests": 0, "bytes": 0, "upstreams": {}})
            rt["requests"] += int(r["cnt"])
            rt["bytes"] += int(r["b"])
            rt["upstreams"][up] = rt["upstreams"].get(up, 0) + int(r["cnt"])

        domains: dict = {}
        for r in conn.execute(
            "SELECT target, COUNT(*) AS cnt, COALESCE(SUM(bytes_in + bytes_out),0) AS b "
            "FROM traffic_log WHERE client = ? AND ts > ? GROUP BY target ORDER BY cnt DESC LIMIT 60",
            (client, cutoff)
        ).fetchall():
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

        hourly_raw: dict = {}
        for r in conn.execute(
            "SELECT CAST(ts / 3600 AS INTEGER) * 3600 AS h, COUNT(*) AS cnt, "
            "COALESCE(SUM(bytes_in + bytes_out),0) AS b "
            "FROM traffic_log WHERE client = ? AND ts > ? GROUP BY h",
            (client, now - 86400)
        ).fetchall():
            hourly_raw[int(r["h"])] = {"requests": int(r["cnt"]), "bytes": int(r["b"])}

        recent_rows = conn.execute(
            "SELECT ts, target, status, upstream, bytes_in, bytes_out, duration, via "
            "FROM traffic_log WHERE client = ? AND ts > ? ORDER BY ts DESC LIMIT 40",
            (client, cutoff)
        ).fetchall()

        return self._client_detail_assemble(summary, routes, domains, hourly_raw,
                                            [dict(r) for r in recent_rows], now)

    def _client_detail_mem(self, client: str, cutoff: float, now: float, hours: int) -> dict:
        rows = [e for e in self._mem_traffic(cutoff) if e.get("client") == client]
        rows.sort(key=lambda e: e.get("ts", 0) or 0, reverse=True)

        requests = len(rows)
        ok = sum(1 for e in rows if (e.get("status") or "") == "ok")
        ts_list = [e.get("ts", 0) or 0 for e in rows]
        summary = {
            "client": client, "hours": hours, "requests": requests,
            "bytes_in": sum(int(e.get("bytes_in", 0) or 0) for e in rows),
            "bytes_out": sum(int(e.get("bytes_out", 0) or 0) for e in rows),
            "ok": ok, "failed": requests - ok,
            "success_rate": round(ok / requests * 100, 1) if requests else 0.0,
            "avg_duration": round(sum(float(e.get("duration", 0) or 0) for e in rows) / requests, 3) if requests else 0.0,
            "first_seen": min(ts_list) if ts_list else 0,
            "last_seen": max(ts_list) if ts_list else 0,
        }
        summary["total_bytes"] = summary["bytes_in"] + summary["bytes_out"]
        summary["hostname"] = _resolve_hostname(client)

        routes: dict = {}
        domains: dict = {}
        hourly_raw: dict = {}
        for e in rows:
            up = e.get("upstream") or ""
            if not up or up == "?":
                up = "unknown"
            rtype = self._route_type(up)
            total = int(e.get("bytes_in", 0) or 0) + int(e.get("bytes_out", 0) or 0)
            rt = routes.setdefault(rtype, {"type": rtype, "requests": 0, "bytes": 0, "upstreams": {}})
            rt["requests"] += 1
            rt["bytes"] += total
            rt["upstreams"][up] = rt["upstreams"].get(up, 0) + 1

            target = e.get("target") or ""
            try:
                host = urlparse(target if target.startswith("http") else f"http://{target}").hostname or target
            except Exception:
                host = target
            if host:
                d = domains.setdefault(host, {"domain": host, "requests": 0, "bytes": 0})
                d["requests"] += 1
                d["bytes"] += total

            hour = int((e.get("ts", 0) or 0) // 3600) * 3600
            b = hourly_raw.setdefault(hour, {"requests": 0, "bytes": 0})
            b["requests"] += 1
            b["bytes"] += total

        return self._client_detail_assemble(summary, routes, domains, hourly_raw, rows[:40], now)

    def _client_detail_assemble(self, summary, routes, domains, hourly_raw, recent_rows, now) -> dict:
        requests = summary["requests"] or 1
        route_list = sorted(routes.values(), key=lambda r: r["requests"], reverse=True)
        for rt in route_list:
            rt["pct"] = round(rt["requests"] / requests * 100, 1)
            rt["top_upstream"] = max(rt["upstreams"], key=rt["upstreams"].get) if rt["upstreams"] else ""

        top_domains = sorted(domains.values(), key=lambda d: d["requests"], reverse=True)[:10]
        for d in top_domains:
            d["pct"] = round(d["requests"] / requests * 100, 1)

        hour_now = int(now // 3600)
        hourly = []
        for h in range(hour_now - 23, hour_now + 1):
            b = hourly_raw.get(h * 3600, {"requests": 0, "bytes": 0})
            hourly.append({"ts": h * 3600, "requests": b["requests"], "bytes": b["bytes"]})

        recent = [{
            "ts": e.get("ts", 0) or 0,
            "target": e.get("target") or "",
            "status": e.get("status") or "",
            "upstream": e.get("upstream") or "",
            "bytes_in": int(e.get("bytes_in", 0) or 0),
            "bytes_out": int(e.get("bytes_out", 0) or 0),
            "duration": float(e.get("duration", 0) or 0),
            "via": e.get("via") or "",
        } for e in recent_rows]

        return {
            "summary": summary,
            "routes": route_list,
            "domains": top_domains,
            "hourly": hourly,
            "recent": recent,
        }
