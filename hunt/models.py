"""Functional split of the huntproxy backend."""

import time
from dataclasses import dataclass, field

@dataclass
class ProxyRating:
    # Proxies that once produced a non-zero speed measurement are kept alive
    # (in the working list and in ratings) for this many consecutive failed
    # checks before being dropped, so a temporary outage does not evict a
    # proven good proxy on the first failure.
    GRACE_FAILS = 100

    address: str
    country: str = ""
    country_code: str = ""
    protocol: str = "http"
    latency_sum: float = 0.0
    latency_count: int = 0
    checks_total: int = 0
    checks_ok: int = 0
    last_check: float = 0.0
    last_ok: float = 0.0
    last_latency: float = 0.0
    last_status: str = "untested"  # ok / failed / untested
    first_seen: float = 0.0
    in_blacklist: bool = False
    blacklist_reason: str = ""
    is_favorite: bool = False
    ip_blacklist_reason: str = ""  # auto-set when egress IP is in a downloaded IP blacklist
    ip_blacklist_hits: int = 0  # number of IP blacklist sources matching the egress IP
    ip_blacklist_sources: list = field(default_factory=list)  # matching source ids
    supports_connect: bool = False
    mitm_suspect: bool = False
    egress_ip: str = ""
    egress_city: str = ""
    egress_isp: str = ""
    egress_country: str = ""
    egress_country_code: str = ""
    listen_country: str = ""
    listen_country_code: str = ""
    listen_city: str = ""
    listen_isp: str = ""
    egress_http_ip: str = ""
    egress_http_country: str = ""
    speed_sum: float = 0.0
    speed_count: int = 0
    last_speed: float = 0.0
    speed_fails: int = 0
    consecutive_fails: int = 0
    source_ids: list = field(default_factory=list)
    ssl_supported: bool = False

    @property
    def speed_avg(self) -> float:
        return self.speed_sum / self.speed_count if self.speed_count else 0.0

    @property
    def latency_avg(self) -> float:
        return self.latency_sum / self.latency_count if self.latency_count else 0.0

    @property
    def success_rate(self) -> float:
        return self.checks_ok / self.checks_total if self.checks_total else 0.0

    @property
    def had_speed(self) -> bool:
        """True if this proxy ever produced a non-zero speed measurement."""
        return self.speed_count > 0

    @property
    def in_grace(self) -> bool:
        """A proven proxy (had speed) within its failure grace period."""
        return self.had_speed and self.consecutive_fails < self.GRACE_FAILS

    @property
    def is_blacklisted(self) -> bool:
        return self.in_blacklist or bool(self.ip_blacklist_reason)

    @property
    def score(self) -> float:
        if self.checks_total == 0:
            return 0.0
        if self.last_status != "ok":
            # A proven proxy (one that once had non-zero speed) stays ranked
            # during its grace period, with the score decaying as consecutive
            # failures accumulate so it sinks gradually rather than vanishing
            # on the first failure.
            if not self.in_grace:
                return 0.0
            grace_ratio = 1.0 - (self.consecutive_fails / self.GRACE_FAILS)
            return max(0.0, self._compute_score() * grace_ratio * 0.5)
        return self._compute_score()

    def _compute_score(self) -> float:
        sr = self.success_rate
        # Reliability and latency matter, but usable speed is the dominant
        # factor for the end user experience.
        base = sr * 40
        if self.latency_count == 0:
            lat_score = 20
        else:
            lat_score = max(0, 100 - self.latency_avg * 10) * 0.2
        result = base + lat_score
        if self.ssl_supported:
            result += 10
        if self.supports_connect:
            result += 5
        if self.mitm_suspect:
            result -= 30
        # Speed is dominant. A non-SOCKS proxy that has never produced a speed
        # measurement is unusable in practice; zero it out instead of letting it
        # linger near the top with a small score from reliability only.
        # SOCKS tunnels cannot use the HTTP speed servers meaningfully, so they
        # are exempt — their score is based on reliability, latency and protocol.
        if self.speed_count == 0 and self.checks_ok > 0:
            port = None
            socks_proxy = False
            try:
                port = int(self.address.rsplit(":", 1)[1])
            except (IndexError, ValueError):
                pass
            if port is not None and port in (1080, 10808, 9050, 4145, 9051):
                socks_proxy = True
            if not socks_proxy:
                # Boost the result upward before subtraction so a strong base
                # does not slip into a small positive score; the requirement is
                # that a no-speed proxy is dropped, not merely demoted.
                result -= max(80, result + 10)
        if self.speed_count > 0:
            result += min(50, self.speed_avg / 20)
        if self.speed_fails > 0:
            result -= min(45, self.speed_fails * 15)
        # Manual operator blacklist is still a hard exclusion.
        if self.in_blacklist:
            return 0.0
        # IP blacklist hits lower the score: more lists -> heavier penalty,
        # but never drop below 20% of the computed score so it remains usable.
        if self.ip_blacklist_hits > 0:
            result *= max(0.2, 0.75 ** self.ip_blacklist_hits)
        return max(0.0, min(100.0, result))

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "country": self.country,
            "country_code": self.country_code,
            "protocol": self.protocol,
            "latency_avg": round(self.latency_avg, 3),
            "latency_sum": round(self.latency_sum, 3),
            "latency_count": self.latency_count,
            "last_latency": round(self.last_latency, 3),
            "checks_total": self.checks_total,
            "checks_ok": self.checks_ok,
            "success_rate": round(self.success_rate, 3),
            "score": round(self.score, 2),
            "speed_avg": round(self.speed_avg, 1),
            "last_speed": round(self.last_speed, 1),
            "speed_sum": round(self.speed_sum, 1),
            "speed_count": self.speed_count,
            "speed_fails": self.speed_fails,
            "consecutive_fails": self.consecutive_fails,
            "in_grace": self.in_grace,
            "last_check": self.last_check,
            "last_status": self.last_status,
            "first_seen": self.first_seen,
            "in_blacklist": self.in_blacklist,
            "blacklist_reason": self.blacklist_reason,
            "is_favorite": self.is_favorite,
            "ip_blacklist_reason": self.ip_blacklist_reason,
            "ip_blacklist_hits": self.ip_blacklist_hits,
            "ip_blacklist_sources": self.ip_blacklist_sources,
            "supports_connect": self.supports_connect,
            "mitm_suspect": self.mitm_suspect,
            "last_check_ago": round(time.time() - self.last_check, 1) if self.last_check else 0,
            "last_ok": self.last_ok,
            "egress_ip": self.egress_ip,
            "egress_city": self.egress_city,
            "egress_isp": self.egress_isp,
            "egress_country": self.egress_country,
            "egress_country_code": self.egress_country_code,
            "listen_country": self.listen_country,
            "listen_country_code": self.listen_country_code,
            "listen_city": self.listen_city,
            "listen_isp": self.listen_isp,
            "ssl_supported": self.ssl_supported,
        }

    def to_pool_dict(self) -> dict:
        """Lightweight dict for the proxy-pool table endpoint.

        Contains only the fields the pool table actually renders, cutting
        response size ~3x vs to_dict (critical when the alive pool is large
        — 12k+ proxies — so the browser fetch doesn't time out).
        """
        return {
            "address": self.address,
            "country": self.country,
            "country_code": self.country_code,
            "protocol": self.protocol,
            "latency_avg": round(self.latency_avg, 3),
            "last_latency": round(self.last_latency, 3),
            "checks_total": self.checks_total,
            "checks_ok": self.checks_ok,
            "success_rate": round(self.success_rate, 3),
            "score": round(self.score, 2),
            "speed_avg": round(self.speed_avg, 1),
            "in_grace": self.in_grace,
            "in_blacklist": self.in_blacklist,
            "is_favorite": self.is_favorite,
            "ip_blacklist_hits": self.ip_blacklist_hits,
            "supports_connect": self.supports_connect,
            "mitm_suspect": self.mitm_suspect,
            "last_ok": self.last_ok,
            "egress_ip": self.egress_ip,
            "egress_city": self.egress_city,
            "egress_isp": self.egress_isp,
            "egress_country": self.egress_country,
            "egress_country_code": self.egress_country_code,
            "listen_country": self.listen_country,
            "listen_country_code": self.listen_country_code,
            "listen_city": self.listen_city,
            "listen_isp": self.listen_isp,
            "ssl_supported": self.ssl_supported,
        }
