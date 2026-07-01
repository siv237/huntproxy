"""Traffic handlers — live traffic, requests/clients/domains/errors, route aggregation.

Also owns the in-memory traffic helpers ``_mem_traffic``, ``_route_type`` and
``_aggregate_routes`` that were previously on ``HuntServer``.
"""

import json
import time
from urllib.parse import urlparse

from hunt.constants import logger


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
            rows = conn.execute("SELECT ts, client, target, status, upstream, bytes_in, bytes_out, duration FROM traffic_log ORDER BY id DESC LIMIT 50").fetchall()
            conn.close()
            db_reqs = [dict(r) for r in rows]
        except Exception:
            db_reqs = []
        reqs = db_reqs if db_reqs else mem
        return json.dumps({"requests": reqs}), 200, "application/json"

    async def _handle_clients(self, raw_path, body):
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
        return json.dumps({"clients": sorted(clients.values(), key=lambda x: x["requests"], reverse=True)[:20]}), 200, "application/json"

    async def _handle_domains(self, raw_path, body):
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
        return json.dumps({"domains": top}), 200, "application/json"

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
        return json.dumps({"errors": result, "total": total}), 200, "application/json"

    async def _handle_traffic_routes(self, raw_path, body):
        cutoff = time.time() - 86400
        entries = []
        try:
            conn = self.state._stats_db()
            rows = conn.execute(
                "SELECT ts, upstream, bytes_in, bytes_out, status, duration "
                "FROM traffic_log WHERE ts > ? ORDER BY id DESC",
                (cutoff,)
            ).fetchall()
            conn.close()
            entries = [dict(r) for r in rows]
        except Exception:
            entries = []
        if not entries:
            entries = self._mem_traffic(cutoff)
        result = self._aggregate_routes(entries)
        return json.dumps({"routes": result}), 200, "application/json"

    async def _handle_bandwidth(self, raw_path, body):
        cutoff = time.time() - 86400
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
        return json.dumps({
            "download": download,
            "upload": upload,
            "total": download + upload,
        }), 200, "application/json"

    async def _handle_traffic_summary(self, raw_path, body):
        periods = {"day": 86400, "week": 604800, "month": 2592000}
        now = time.time()
        conn = None
        try:
            conn = self.state._stats_db()
        except Exception as e:
            logger.error("traffic/summary: %s", e)
        result = {}
        for name, secs in periods.items():
            result[name] = self._compute_traffic_period(conn, name, now, secs)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("suppressed", exc_info=True)
        return json.dumps(result), 200, "application/json"

    def _compute_traffic_period(self, conn, name, now, secs):
        cutoff = now - secs
        download = upload = reqs = ok = 0
        routes = []
        used_db = False
        if conn is not None:
            try:
                row = conn.execute(
                    "SELECT COALESCE(SUM(bytes_in),0) as bin, COALESCE(SUM(bytes_out),0) as bout, "
                    "COUNT(*) as reqs, "
                    "COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END),0) as ok "
                    "FROM traffic_log WHERE ts > ?", (cutoff,)
                ).fetchone()
                download = int(row["bout"] or 0)
                upload = int(row["bin"] or 0)
                reqs = int(row["reqs"] or 0)
                ok = int(row["ok"] or 0)
                if reqs > 0:
                    used_db = True
                    routes = self._top_routes_from_db(conn, cutoff)
            except Exception:
                used_db = False
        if not used_db and name == "day":
            entries = self._mem_traffic(cutoff)
            for e in entries:
                upload += int(e.get("bytes_in", 0) or 0)
                download += int(e.get("bytes_out", 0) or 0)
                reqs += 1
                if (e.get("status") or "") == "ok":
                    ok += 1
            routes = self._top_routes_from_mem(entries)
        return {
            "download": download, "upload": upload,
            "total": download + upload, "requests": reqs,
            "success": ok, "failed": reqs - ok,
            "success_rate": round(ok / reqs * 100, 1) if reqs else 0,
            "top_routes": routes,
        }

    def _top_routes_from_db(self, conn, cutoff):
        routes = []
        for rr in conn.execute(
            "SELECT upstream, COUNT(*) as cnt, "
            "COALESCE(SUM(bytes_in),0) as bin, COALESCE(SUM(bytes_out),0) as bout "
            "FROM traffic_log WHERE ts > ? GROUP BY upstream ORDER BY cnt DESC LIMIT 5",
            (cutoff,)
        ).fetchall():
            up = rr["upstream"] or "unknown"
            routes.append({
                "type": self._route_type(up), "upstream": up,
                "requests": int(rr["cnt"]),
                "bytes": int(rr["bout"] or 0) + int(rr["bin"] or 0),
            })
        return routes

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
