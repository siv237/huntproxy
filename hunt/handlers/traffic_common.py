"""Shared constants and helpers for the split traffic handlers."""

import socket
import time

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

# Full-text traffic search (/api/traffic/search). The LIKE-style scan runs
# over every row in the time window; a short per-query TTL keeps the 2s UI
# poll from hammering the DB while staying fresh enough for live filtering.
_SEARCH_TTL = 5.0
_SEARCH_CACHE: dict = {}
_SEARCH_REFRESHING: set = set()


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
