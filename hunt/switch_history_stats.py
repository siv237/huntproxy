"""Traffic/duration aggregation for proxy switch history.

Extracted from switch_history.py to keep that module within its size budget.
"""

import logging

logger = logging.getLogger(__name__)


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

    All intervals are covered by ONE query: each interval contributes a
    ``SUM(CASE ...)`` column, so SQLite buckets every row into its owning
    interval at C speed.  The previous per-row Python bisect pass shipped
    the whole 24h window into the interpreter on every /api/proxy/status
    poll, which stacked up concurrent polls and starved the server."""
    intervals = _intervals(chronological, now)
    if not intervals:
        return {}
    result: dict[int, int] = {j: 0 for j in intervals}
    # chronological order ⇒ the earliest start wins
    first = min(v[0] for v in intervals.values())
    # Never aggregate more than the last 24h: switch history can span days,
    # and a multi-day scan over traffic_log stalls the whole server.
    first = max(first, now - 86400)

    def _like(addr: str) -> str:
        # addresses are ip:port — no LIKE wildcards to escape
        return "%:" + addr

    cols = []
    args: list = []
    for j, (start, end, addr) in intervals.items():
        s = max(start, first)
        e = min(end, now + 1)
        if not addr or s >= e:
            continue
        cols.append(
            "SUM(CASE WHEN ts >= ? AND ts < ? AND (upstream = ? OR upstream LIKE ?) "
            "THEN COALESCE(bytes_in,0) + COALESCE(bytes_out,0) ELSE 0 END)"
        )
        args.extend((s, e, addr, _like(addr)))
    if not cols:
        return result
    sql = "SELECT " + ", ".join(cols) + " FROM traffic_log WHERE ts >= ? AND ts < ?"  # nosec B608 — cols generated, all values bound
    args.extend((first, now + 1))
    try:
        import sqlite3
        conn = sqlite3.connect(str(state._db_path), check_same_thread=False)
        try:
            row = conn.execute(sql, args).fetchone()
            i = 0
            for j, (start, end, addr) in intervals.items():
                s = max(start, first)
                e = min(end, now + 1)
                if not addr or s >= e:
                    continue
                result[j] = int(row[i] or 0) if row else 0
                i += 1
        finally:
            conn.close()
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return result


def _period_durations(chronological: list[dict], now: float) -> dict[int, float]:
    """Map chronological entry index → seconds that proxy was active."""
    intervals = _intervals(chronological, now)
    return {j: max(0, end - start) for j, (start, end, _a) in intervals.items()}
