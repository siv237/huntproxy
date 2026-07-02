"""Proxy switch history enrichment — extracted from proxy_runner.py.

Builds the timeline of upstream switches shown in the proxy-pool UI:
collapses consecutive duplicates, enriches each row with proxy metadata
from ratings, and sums traffic served during each entry's active period.
"""

import logging
import time

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 500
_SEP = ":"


def record_switch(history: list[dict], action: str, address: str) -> None:
    """Append an entry to the proxy switch history chronology."""
    entry = {"ts": time.time(), "action": action, "address": address or ""}
    history.append(entry)
    if len(history) > _HISTORY_LIMIT:
        del history[:-_HISTORY_LIMIT]


def enrich_switch_history(state) -> list[dict]:
    """Return switch history (newest first) enriched with proxy details
    and traffic served during each entry's active period.

    Consecutive entries with the same action + address are collapsed
    into one row (keeping the earliest ts) so the timeline shows only
    actual switches, not repeated re-selections of the same proxy.

    Each merged entry covers [ts_j, ts_{j+1}) — from this switch until
    the next different one (or now for the latest).  Traffic is summed
    from traffic_log rows whose upstream chain includes the proxy
    address as a token and whose ts falls within that interval.
    """
    hist = state._proxy_switch_history[-_HISTORY_LIMIT:]
    if not hist:
        return []
    now = time.time()
    merged = _merge_consecutive(hist)
    traffic = _traffic_by_period(state, merged, now)
    durations = _period_durations(merged, now)
    ratings = state.ratings
    n = len(merged)
    out = []
    for j, e in enumerate(reversed(merged)):
        idx = n - 1 - j
        addr = e.get("address", "")
        r = ratings.get(addr)
        row = dict(e)
        if r and addr:
            row["protocol"] = r.protocol
            row["ssl_supported"] = r.ssl_supported
            row["egress_ip"] = r.egress_ip
            row["egress_country"] = r.egress_country
            row["egress_country_code"] = r.egress_country_code
            row["egress_city"] = r.egress_city
            row["egress_isp"] = r.egress_isp
            row["speed_avg"] = r.speed_avg
            row["last_latency"] = r.last_latency
            row["is_favorite"] = r.is_favorite
        row["bytes"] = traffic.get(idx, 0)
        row["duration_sec"] = durations.get(idx, 0)
        out.append(row)
    return out


def _merge_consecutive(hist: list[dict]) -> list[dict]:
    """Collapse consecutive entries with the same action + address,
    keeping the earliest ts of each group."""
    merged: list[dict] = []
    for e in hist:
        if merged and merged[-1].get("action") == e.get("action") \
                and merged[-1].get("address") == e.get("address"):
            continue
        merged.append(dict(e))
    return merged


def _intervals(chronological: list[dict], now: float) -> dict[int, tuple[float, float, str]]:
    """Map chronological entry index → (start, end, address) active period."""
    intervals: dict[int, tuple[float, float, str]] = {}
    n = len(chronological)
    for j, e in enumerate(chronological):
        start = e["ts"]
        end = chronological[j + 1]["ts"] if j + 1 < n else now
        intervals[j] = (start, end, e.get("address", ""))
    return intervals


def _traffic_by_period(state, chronological: list[dict], now: float) -> dict[int, int]:
    """Map chronological entry index → total bytes served while that
    proxy was active (until the next switch or now).

    The upstream column stores a prefixed form such as ``proxy:ADDR``,
    ``pool:ADDR`` or ``custom:NAME`` — a label, a colon, then the
    address.  We match the address as a suffix after the colon
    (``%:ADDR``) so ``1.2.3.4:1080`` does not match ``11.2.3.4:1080``.
    A bare-address row (no prefix) is matched exactly too.
    """
    intervals = _intervals(chronological, now)
    if not intervals:
        return {}
    result: dict[int, int] = {j: 0 for j in intervals}
    try:
        conn = state._stats_db()
        for j, (start, end, addr) in intervals.items():
            if not addr or end <= start:
                continue
            row = conn.execute(
                "SELECT COALESCE(SUM(bytes_in),0) + COALESCE(SUM(bytes_out),0) "
                "FROM traffic_log WHERE ts >= ? AND ts < ? AND "
                "(upstream = ? OR upstream LIKE ?)",
                (start, end, addr, "%" + _SEP + addr),
            ).fetchone()
            result[j] = int(row[0]) if row else 0
        conn.close()
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return result


def _period_durations(chronological: list[dict], now: float) -> dict[int, float]:
    """Map chronological entry index → seconds that proxy was active."""
    intervals = _intervals(chronological, now)
    return {j: max(0, end - start) for j, (start, end, _a) in intervals.items()}
