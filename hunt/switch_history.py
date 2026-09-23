"""Proxy switch history enrichment — extracted from proxy_runner.py.

Builds the timeline of upstream switches shown in the proxy-pool UI:
collapses consecutive duplicates, enriches each row with proxy metadata
from ratings, and sums traffic served during each entry's active period.
"""

import logging
import time

from hunt.switch_history_stats import _period_durations, _traffic_by_period

logger = logging.getLogger(__name__)

_HISTORY_LIMIT = 500
# Kinds recorded for the effective (user-traffic) upstream path.  Manual
# selections use "select", the automatic pool "pool"/"fallback", direct and
# the legacy clear path "direct".
_EFFECTIVE_KINDS = ("select", "pool", "fallback", "direct")
# Memoize enrich_switch_history for this long; the proxy-status endpoint is
# polled every couple of seconds but old switch intervals never change their
# traffic retroactively, so recomputing the whole traffic_log scan each poll
# is pure waste. A new switch changes the signature and forces a recompute.
_TRAFFIC_CACHE_TTL = 10.0


def record_switch(history: list[dict], action: str, address: str) -> None:
    """Append an entry to the proxy switch history chronology."""
    entry = {"ts": time.time(), "action": action, "address": address or ""}
    history.append(entry)
    if len(history) > _HISTORY_LIMIT:
        del history[:-_HISTORY_LIMIT]


def effective_from_chain(chain: list) -> tuple:
    """Map a connection chain to the (address, kind) that actually carried
    the request — the last token: ``pool:ADDR``, ``proxy:ADDR`` or ``direct``.

    A chain that rerouted after the selected proxy failed is marked
    ``fallback`` so the history tells an auto-failover from a plain pick.
    """
    if not chain:
        return "", ""
    tok = str(chain[-1])
    fallback = any("fallback" in str(c) for c in chain)
    if tok.startswith("pool:"):
        addr = tok[5:].split(" (", 1)[0].strip()
        return addr, ("fallback" if fallback else "pool")
    if tok.startswith("proxy:"):
        return tok[6:].split(" (", 1)[0].strip(), "select"
    if tok.startswith("direct"):
        return "", "direct"
    return "", ""


def record_effective_upstream(state, addr: str, kind: str) -> None:
    """Remember the proxy that really carried traffic and append a switch
    entry when the carrier changes.

    Without this the switch history and the topbar ping badge only ever
    reflected manually selected proxies — automatic pool picks and failover
    reroutes stayed invisible even though they served most of the traffic.
    """
    if kind not in _EFFECTIVE_KINDS:
        return
    addr = addr or ""
    prev = getattr(state, "_effective_upstream", None) or {}
    if prev.get("addr", "") == addr and prev.get("kind", "") == kind:
        return
    state._effective_upstream = {"addr": addr, "kind": kind, "ts": time.time()}
    record_switch(state._proxy_switch_history, kind, addr)


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
    sig = (len(hist), hist[-1].get("ts"), int(now // _TRAFFIC_CACHE_TTL))
    cache = getattr(state, "_switch_hist_cache", None)
    if cache is not None and cache[0] == sig:
        return cache[1]
    out = _build_switch_history(state, hist, now)
    state._switch_hist_cache = (sig, out)
    return out


def _build_switch_history(state, hist, now) -> list[dict]:
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
            row["egress_country"] = r.egress_country_code
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

