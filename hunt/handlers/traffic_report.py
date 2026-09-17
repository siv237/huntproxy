"""Traffic report handlers (domains/errors/routes/bandwidth) — split from traffic.py."""

import asyncio
import json
import time
from urllib.parse import urlparse


class TrafficReportMixin:
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
