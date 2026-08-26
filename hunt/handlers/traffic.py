"""Traffic handlers — live traffic, requests/clients/domains/errors, route aggregation.

Also owns the in-memory traffic helpers ``_mem_traffic``, ``_route_type`` and
``_aggregate_routes`` that were previously on ``HuntServer``.
"""

import asyncio
import json
import socket
import time
from urllib.parse import unquote, urlparse

from hunt.constants import logger
from hunt.handlers import _int_param, _qs

# Memoize /api/traffic/summary for this long. It scans traffic_log three times
# per request and the dashboard polls it every couple of seconds; the data is
# only shown at second-grained resolution, so a short TTL is indistinguishable
# to the user while killing the per-poll DB load.
_SUMMARY_TTL = 10.0

# Reverse-DNS cache: ip -> (resolved_at, hostname-or-""). Negative results are
# cached too — most LAN IPs have no PTR record and re-resolving them on every
# poll would hammer the resolver. Hostnames change (DHCP), hence the TTL.
_DNS_TTL = 600.0
_DNS_CACHE: dict = {}


def _resolve_hostname(ip: str) -> str:
    if not ip or ip == "?":
        return ""
    if ip.startswith("127.") or ip in ("::1", "localhost"):
        return "localhost"
    now = time.monotonic()
    cached = _DNS_CACHE.get(ip)
    if cached is not None and now - cached[0] < _DNS_TTL:
        return cached[1]
    try:
        host = socket.gethostbyaddr(ip)[0]
    except Exception:
        host = ""
    _DNS_CACHE[ip] = (now, host)
    return host


class TrafficHandlers:
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

    async def _handle_domains(self, raw_path, body):
        # GROUP BY over the full traffic_log — keep it off the event loop.
        return json.dumps(await asyncio.to_thread(self._domains_payload)), 200, "application/json"

    def _domains_payload(self):
        domains = {}
        try:
            conn = self.state._stats_db()
            rows = conn.execute("SELECT target, COUNT(*) as requests FROM traffic_log WHERE client != '?' GROUP BY target ORDER BY requests DESC LIMIT 50").fetchall()
            conn.close()
            for r in rows:
                t = r["target"]
                try:
                    h = urlparse(t if t.startswith("http") else f"http://{t}").hostname or t
                except Exception:
                    h = t
                if not h:
                    continue
                if h not in domains:
                    domains[h] = {"domain": h, "requests": 0}
                domains[h]["requests"] += r["requests"]
        except Exception:
            for entry in self.server.proxy.log:
                t = entry.get("target", "")
                try:
                    h = urlparse(t if t.startswith("http") else f"http://{t}").hostname or t
                except Exception:
                    h = t
                if not h:
                    continue
                if h not in domains:
                    domains[h] = {"domain": h, "requests": 0}
                domains[h]["requests"] += 1
        top = sorted(domains.values(), key=lambda x: x["requests"], reverse=True)[:10]
        total = sum(d["requests"] for d in top) or 1
        for d in top:
            d["pct"] = round(d["requests"] / total * 100, 1)
        return {"domains": top}

    def _classify_error(self, st: str) -> str:
        sl = st.lower()
        if "timeout" in sl:
            return "timeout"
        if "connect" in sl or "fail" in sl:
            return "connect_failed"
        if st.startswith("4"):
            return "4xx"
        if st.startswith("5"):
            return "5xx"
        return "other"

    async def _handle_errors(self, raw_path, body):
        # GROUP BY over the full traffic_log — keep it off the event loop.
        return json.dumps(await asyncio.to_thread(self._errors_payload)), 200, "application/json"

    def _errors_payload(self):
        errors = {"timeout": 0, "connect_failed": 0, "4xx": 0, "5xx": 0, "other": 0}
        try:
            conn = self.state._stats_db()
            rows = conn.execute("SELECT status, COUNT(*) as cnt FROM traffic_log WHERE status != 'ok' GROUP BY status").fetchall()
            conn.close()
            for r in rows:
                errors[self._classify_error(r["status"])] += r["cnt"]
        except Exception:
            for entry in self.server.proxy.log:
                errors[self._classify_error(entry.get("status", ""))] += 1
        total = sum(errors.values()) or 1
        result = [{"type": k, "count": v, "pct": round(v / total * 100, 1)} for k, v in errors.items() if v]
        return {"errors": result, "total": total}

    async def _handle_traffic_routes(self, raw_path, body):
        # Pulls every row of the 24h window out of traffic_log — keep it off
        # the event loop.
        return json.dumps(await asyncio.to_thread(self._routes_payload)), 200, "application/json"

    def _routes_payload(self):
        cutoff = time.time() - 86400
        agg = getattr(self.state, "_traffic_stats", None)
        if agg is not None and agg.ready:
            rows = [{"upstream": up, "_cnt": r[0], "bytes_in": r[1],
                     "bytes_out": r[2], "_ok": r[3], "_dur_sum": r[4]}
                    for up, r in agg.by_upstream(cutoff).items()]
            if rows:
                return {"routes": self._aggregate_rollup(rows)}
        entries = []
        try:
            conn = self.state._stats_db()
            # Aggregate in SQLite: grouping millions of raw rows in C beats
            # shipping every row into Python just to count them.
            rows = conn.execute(
                "SELECT upstream, COUNT(*) AS cnt, "
                "COALESCE(SUM(bytes_in),0) AS bin, COALESCE(SUM(bytes_out),0) AS bout, "
                "COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END),0) AS okc, "
                "COALESCE(SUM(duration),0) AS durs "
                "FROM traffic_log WHERE ts > ? GROUP BY upstream",
                (cutoff,)
            ).fetchall()
            conn.close()
            entries = [{
                "upstream": r["upstream"], "_cnt": int(r["cnt"]),
                "bytes_in": int(r["bin"]), "bytes_out": int(r["bout"]),
                "_ok": int(r["okc"]), "_dur_sum": float(r["durs"]),
            } for r in rows]
        except Exception:
            entries = []
        if not entries:
            return {"routes": self._aggregate_routes(self._mem_traffic(cutoff))}
        return {"routes": self._aggregate_rollup(entries)}

    def _aggregate_rollup(self, rows: list) -> list:
        """Route-type buckets from pre-aggregated per-upstream rows."""
        routes: dict = {}
        for e in rows:
            up = e.get("upstream") or ""
            if not up or up == "?":
                up = "unknown"
            rtype = self._route_type(up)
            rt = routes.setdefault(rtype, {
                "type": rtype, "requests": 0, "bytes_in": 0, "bytes_out": 0,
                "ok": 0, "_dur_sum": 0.0, "upstreams": {},
            })
            rt["requests"] += e["_cnt"]
            rt["bytes_in"] += e["bytes_in"]
            rt["bytes_out"] += e["bytes_out"]
            rt["ok"] += e["_ok"]
            rt["_dur_sum"] += e["_dur_sum"]
            rt["upstreams"][up] = e["_cnt"]
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

    async def _handle_bandwidth(self, raw_path, body):
        return json.dumps(await asyncio.to_thread(self._bandwidth_payload)), 200, "application/json"

    def _bandwidth_payload(self):
        cutoff = time.time() - 86400
        agg = getattr(self.state, "_traffic_stats", None)
        if agg is not None and agg.ready:
            # totals: [requests, upload(bytes_in), download(bytes_out), ok]
            reqs, upload, download, _ok = agg.totals(cutoff)
            if reqs > 0:
                return {
                    "download": download,
                    "upload": upload,
                    "total": download + upload,
                }
        upload = 0
        download = 0
        have_db = False
        try:
            conn = self.state._stats_db()
            row = conn.execute(
                "SELECT COALESCE(SUM(bytes_in),0) as bin, COALESCE(SUM(bytes_out),0) as bout "
                "FROM traffic_log WHERE ts > ?",
                (cutoff,)
            ).fetchone()
            conn.close()
            upload = int(row["bin"] if row else 0)    # bytes_in  = client→upstream = upload
            download = int(row["bout"] if row else 0)  # bytes_out = upstream→client = download
            have_db = (upload + download) > 0
        except Exception:
            have_db = False
        if not have_db:
            upload = 0
            download = 0
            for e in self._mem_traffic(cutoff):
                upload += int(e.get("bytes_in", 0) or 0)
                download += int(e.get("bytes_out", 0) or 0)
        return {
            "download": download,
            "upload": upload,
            "total": download + upload,
        }

    async def _handle_traffic_summary(self, raw_path, body):
        now = time.time()
        bucket = int(now // _SUMMARY_TTL)
        cache = getattr(self.state, "_traffic_summary_cache", None)
        if cache is not None and cache[0] == bucket:
            return cache[1], 200, "application/json"
        # Three range scans + GROUP BY over traffic_log — keep them off the
        # event loop so a cache miss can't freeze every other page.
        payload = await asyncio.to_thread(self._summary_payload, now)
        self.state._traffic_summary_cache = (bucket, payload)
        return payload, 200, "application/json"

    def _summary_payload(self, now):
        d_cut = now - 86400
        w_cut = now - 604800
        m_cut = now - 2592000
        result = {name: self._empty_period() for name in ("day", "week", "month")}

        agg = getattr(self.state, "_traffic_stats", None)
        if agg is not None and agg.ready:
            # One fold over hourly counters covers all three periods.
            acc = {name: {} for name in result}
            for h, buckets in agg.iter_hours():
                if h < m_cut:
                    continue
                for up, row in buckets.items():
                    for name, cut in (("day", d_cut), ("week", w_cut), ("month", m_cut)):
                        if h < cut:
                            continue
                        b = acc[name].setdefault(up, [0, 0, 0, 0])
                        b[0] += row[0]
                        b[1] += row[1]
                        b[2] += row[2]
                        b[3] += row[3]
            for name, rows in acc.items():
                p = result[name]
                items = sorted(rows.items(), key=lambda x: x[1][0], reverse=True)
                for up, (c, bi, bo, okc) in items:
                    self._period_add(p, c, bi, bo, okc)
                    if len(p["top_routes"]) < 5:
                        p["top_routes"].append({
                            "type": self._route_type(up), "upstream": up or "unknown",
                            "requests": c, "bytes": bi + bo,
                        })
            if result["day"]["requests"] == 0:
                entries = self._mem_traffic(d_cut)
                upload = download = reqs = ok = 0
                for e in entries:
                    upload += int(e.get("bytes_in", 0) or 0)
                    download += int(e.get("bytes_out", 0) or 0)
                    reqs += 1
                    if (e.get("status") or "") == "ok":
                        ok += 1
                if reqs:
                    result["day"] = {
                        "download": download, "upload": upload,
                        "total": download + upload, "requests": reqs,
                        "success": ok, "failed": reqs - ok,
                        "success_rate": round(ok / reqs * 100, 1),
                        "top_routes": self._top_routes_from_mem(entries),
                    }
            return json.dumps(result)

        # Fallback: rollup not ready (fresh state / load failure) — one raw
        # range scan with per-period conditional SUMs in SQLite.
        periods = {"day": 0, "week": 0, "month": 0}
        conn = None
        try:
            conn = self.state._stats_db()
        except Exception as e:
            logger.error("traffic/summary: %s", e)
        rows = []
        if conn is not None:
            try:
                rows = conn.execute(
                    "SELECT upstream, "
                    "SUM(CASE WHEN ts > ? THEN 1 ELSE 0 END) AS d_cnt, "
                    "COALESCE(SUM(CASE WHEN ts > ? THEN bytes_in ELSE 0 END),0) AS d_bin, "
                    "COALESCE(SUM(CASE WHEN ts > ? THEN bytes_out ELSE 0 END),0) AS d_bout, "
                    "COALESCE(SUM(CASE WHEN ts > ? AND status='ok' THEN 1 ELSE 0 END),0) AS d_ok, "
                    "SUM(CASE WHEN ts > ? THEN 1 ELSE 0 END) AS w_cnt, "
                    "COALESCE(SUM(CASE WHEN ts > ? THEN bytes_in ELSE 0 END),0) AS w_bin, "
                    "COALESCE(SUM(CASE WHEN ts > ? THEN bytes_out ELSE 0 END),0) AS w_bout, "
                    "COALESCE(SUM(CASE WHEN ts > ? AND status='ok' THEN 1 ELSE 0 END),0) AS w_ok, "
                    "COUNT(*) AS m_cnt, "
                    "COALESCE(SUM(bytes_in),0) AS m_bin, "
                    "COALESCE(SUM(bytes_out),0) AS m_bout, "
                    "COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END),0) AS m_ok "
                    "FROM traffic_log WHERE ts > ? GROUP BY upstream",
                    (d_cut, d_cut, d_cut, d_cut,
                     w_cut, w_cut, w_cut, w_cut, m_cut)
                ).fetchall()
            except Exception:
                logger.debug("suppressed", exc_info=True)
            finally:
                try:
                    conn.close()
                except Exception:
                    logger.debug("suppressed", exc_info=True)

        def _fill(prefix, name):
            p = result[name]
            for r in rows:
                cnt = int(r[f"{prefix}_cnt"] or 0)
                if cnt <= 0:
                    continue
                bin_ = int(r[f"{prefix}_bin"] or 0)
                bout = int(r[f"{prefix}_bout"] or 0)
                okc = int(r[f"{prefix}_ok"] or 0)
                up = r["upstream"] or "unknown"
                self._period_add(p, cnt, bin_, bout, okc)
                if len(p["top_routes"]) < 5:
                    p["top_routes"].append({
                        "type": self._route_type(up), "upstream": up,
                        "requests": cnt, "bytes": bout + bin_,
                    })

        _fill("d", "day")
        _fill("w", "week")
        _fill("m", "month")

        # Old behavior preserved: the "day" tile falls back to the in-memory
        # proxy log whenever its own window has no DB rows, so the widgets
        # stay populated while the DB is empty or lagging.
        if result["day"]["requests"] == 0:
            entries = self._mem_traffic(d_cut)
            upload = download = reqs = ok = 0
            for e in entries:
                upload += int(e.get("bytes_in", 0) or 0)
                download += int(e.get("bytes_out", 0) or 0)
                reqs += 1
                if (e.get("status") or "") == "ok":
                    ok += 1
            result["day"] = {
                "download": download, "upload": upload,
                "total": download + upload, "requests": reqs,
                "success": ok, "failed": reqs - ok,
                "success_rate": round(ok / reqs * 100, 1) if reqs else 0,
                "top_routes": self._top_routes_from_mem(entries),
            }
        return json.dumps(result)

    @staticmethod
    def _empty_period():
        return {"download": 0, "upload": 0, "total": 0, "requests": 0,
                "success": 0, "failed": 0, "success_rate": 0, "top_routes": []}

    @staticmethod
    def _period_add(p, cnt, bin_, bout, okc):
        p["requests"] += cnt
        p["upload"] += bin_
        p["download"] += bout
        p["total"] += bin_ + bout
        p["success"] += okc
        p["failed"] += cnt - okc
        p["success_rate"] = round(p["success"] / p["requests"] * 100, 1) if p["requests"] else 0

    def _top_routes_from_mem(self, entries):
        routes = []
        for r in self._aggregate_routes(entries)[:5]:
            up = r["upstreams"][0]["upstream"] if r["upstreams"] else r["type"]
            routes.append({
                "type": r["type"], "upstream": up,
                "requests": r["requests"],
                "bytes": r["bytes_in"] + r["bytes_out"],
            })
        return routes
