"""Dashboard traffic summary — extracted from handlers/traffic.py.

The one big ``_summary_payload`` was split into focused helpers (rollup fold,
raw-SQL fallback, in-memory day fallback) so each stays under the complexity
budget.
"""

import asyncio
import json
import time

from hunt.constants import logger
from hunt.handlers.traffic_common import _SUMMARY_TTL


class TrafficSummaryMixin:
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
            self._summary_from_rollup(result, agg, d_cut, w_cut, m_cut)
            self._summary_day_from_mem(result, d_cut)
            return json.dumps(result)

        # Fallback: rollup not ready (fresh state / load failure) — one raw
        # range scan with per-period conditional SUMs in SQLite.
        self._summary_from_db(result, d_cut, w_cut, m_cut)
        self._summary_day_from_mem(result, d_cut)
        return json.dumps(result)

    def _summary_from_rollup(self, result, agg, d_cut, w_cut, m_cut):
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

    def _summary_from_db(self, result, d_cut, w_cut, m_cut):
        rows = self._summary_query(d_cut, w_cut, m_cut)

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

    def _summary_query(self, d_cut, w_cut, m_cut):
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
        return rows

    def _summary_day_from_mem(self, result, d_cut):
        # Old behavior preserved: the "day" tile falls back to the in-memory
        # proxy log whenever its own window has no DB rows, so the widgets
        # stay populated while the DB is empty or lagging.
        if result["day"]["requests"] != 0:
            return
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
