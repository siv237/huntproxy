"""In-memory hourly rollup of proxied traffic.

Every proxied request is already funnelled through
``DbMixin._queue_traffic_log``; this module folds each row into
hour/upstream counters at O(1) cost so dashboard endpoints never have to
re-scan the multi-million-row ``traffic_log`` table. The counters are
rebuilt once at startup with a single GROUP BY and kept warm incrementally
afterwards.

Granularity note: counters are bucketed by whole hours, so period totals
(cut off mid-hour) can differ from an exact SQL scan by up to one hour of
data — invisible at tile resolution, irrelevant next to being ~1000x
cheaper.
"""

import logging
import time

logger = logging.getLogger(__name__)


class TrafficStats:
    HOUR = 3600
    # Keep a bit more than the summary's 30-day window so period math near
    # the boundary stays correct between prunes.
    WINDOW = 35 * 86400
    _PRUNE_EVERY = 600.0
    _PRUNE_THRESHOLD = 900

    def __init__(self):
        # hour_start -> {upstream: [cnt, bytes_in, bytes_out, ok, dur_sum]}
        self._hours: dict[int, dict[str, list]] = {}
        self._last_prune = 0.0
        self.ready = False

    def add(self, ts, status, upstream, bytes_in, bytes_out, duration=0.0):
        try:
            h = int(ts // self.HOUR) * self.HOUR
            buckets = self._hours.get(h)
            if buckets is None:
                if len(self._hours) > self._PRUNE_THRESHOLD and \
                        time.time() - self._last_prune > self._PRUNE_EVERY:
                    self.prune(time.time())
                buckets = self._hours[h] = {}
            if not upstream:
                upstream = ""
            row = buckets.get(upstream)
            if row is None:
                row = buckets[upstream] = [0, 0, 0, 0, 0.0]
            row[0] += 1
            row[1] += int(bytes_in or 0)
            row[2] += int(bytes_out or 0)
            if (status or "") == "ok":
                row[3] += 1
            row[4] += float(duration or 0.0)
        except Exception:
            logger.debug("suppressed", exc_info=True)

    def prune(self, now: float):
        lo = now - self.WINDOW
        for h in [h for h in self._hours if h < lo]:
            del self._hours[h]
        self._last_prune = now

    def iter_hours(self):
        return self._hours.items()

    def totals(self, cutoff: float) -> list:
        """[requests, bytes_in, bytes_out, ok] summed over hours >= cutoff."""
        out = [0, 0, 0, 0]
        for h, buckets in self._hours.items():
            if h < cutoff:
                continue
            for row in buckets.values():
                out[0] += row[0]
                out[1] += row[1]
                out[2] += row[2]
                out[3] += row[3]
        return out

    def by_upstream(self, cutoff: float) -> dict[str, list]:
        """upstream -> [cnt, bytes_in, bytes_out, ok, dur_sum], hours >= cutoff."""
        out: dict[str, list] = {}
        for h, buckets in self._hours.items():
            if h < cutoff:
                continue
            for up, row in buckets.items():
                acc = out.get(up)
                if acc is None:
                    acc = out[up] = [0, 0, 0, 0, 0.0]
                acc[0] += row[0]
                acc[1] += row[1]
                acc[2] += row[2]
                acc[3] += row[3]
                acc[4] += row[4]
        return out

    def load_from_db(self, conn, now: float):
        """Rebuild all counters from traffic_log with one grouped scan."""
        try:
            since = now - self.WINDOW
            cur = conn.execute(
                "SELECT CAST(ts/? AS INTEGER)*? AS h, upstream, COUNT(*) AS c, "
                "COALESCE(SUM(bytes_in),0) AS bi, COALESCE(SUM(bytes_out),0) AS bo, "
                "COALESCE(SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END),0) AS okc, "
                "COALESCE(SUM(duration),0) AS durs "
                "FROM traffic_log WHERE ts > ? GROUP BY h, upstream",
                (self.HOUR, self.HOUR, since),
            )
            for h, up, c, bi, bo, okc, durs in cur:
                buckets = self._hours.get(int(h))
                if buckets is None:
                    buckets = self._hours[int(h)] = {}
                if not up:
                    up = ""
                row = buckets.get(up)
                if row is None:
                    row = buckets[up] = [0, 0, 0, 0, 0.0]
                row[0] += int(c)
                row[1] += int(bi)
                row[2] += int(bo)
                row[3] += int(okc)
                row[4] += float(durs)
            self.prune(now)
            self.ready = True
        except Exception:
            logger.debug("suppressed", exc_info=True)
