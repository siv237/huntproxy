"""Functional split of the huntproxy backend."""

import time
from dataclasses import dataclass, field

@dataclass
class ProxyRating:
    # Proxies that once produced a non-zero speed measurement are kept alive
    # (in the working list and in ratings) for this many consecutive failed
    # checks before being dropped, so a temporary outage does not evict a
    # proven good proxy on the first failure.
    GRACE_FAILS = 50

    # EWMA factor for recency-weighted reliability/latency/speed: effective
    # window is roughly the last 10-15 measurements, so degraded proxies sink
    # and recovered ones climb back within a few health cycles instead of
    # keeping lifetime averages forever.
    EWMA_ALPHA = 0.25
    # Anti-fraud is dynamic: a verdict (clean or accusation) older than this
    # no longer counts as verified. Fraud is re-fetched on every proxy
    # re-check; once the window lapses without a fresh confirmation the
    # proxy drops into the unverified bucket instead of riding an old
    # verdict for weeks.
    FRAUD_FRESH_SECONDS = 6 * 3600.0
    # Score multiplier while fraud status is unverified: never checked,
    # expired window, or the last attempt produced no data (refused /
    # timed out). Sits below any confirmed CLEAN proxy so unverified
    # nodes cannot top the pool, but above confirmed accusations.
    FRAUD_UNKNOWN_FACTOR = 0.9
    # Real-traffic failures update the reliability EWMA at most once per this
    # interval: one user page load can produce several connection errors, and
    # each should not count as an independent failed check.
    TRAFFIC_FAIL_THROTTLE = 5.0

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
    fraud_hosting: bool = False  # egress-IP за дата-центром/хостингом (ip-api hosting)
    fraud_proxy: bool = False  # egress-IP помечен как прокси/VPN (ip-api proxy)
    fraud_mobile: bool = False  # egress-IP мобильный оператор/CGNAT (ip-api mobile)
    fraud_score_raw: int = -1  # риск 0-100 напрямую от proxycheck.io; -1 = нет
    fraud_checked_ts: float = 0.0  # когда в последний раз получали fraud-данные
    fraud_attempt_ts: float = 0.0  # когда последняя попытка проверки не дала данных
    speed_sum: float = 0.0
    speed_count: int = 0
    last_speed: float = 0.0
    speed_fails: int = 0
    consecutive_fails: int = 0
    source_ids: list = field(default_factory=list)
    ssl_supported: bool = False
    sr_ewma: float = -1.0        # EWMA успеха; <0 — не инициализирован (сид из lifetime)
    latency_ewma: float = -1.0   # EWMA задержки, сек; <0 — нет данных
    speed_ewma: float = -1.0     # EWMA скорости, KB/s; <0 — нет данных
    last_traffic_fail_ts: float = 0.0  # троттлинг трафик-фейлов для EWMA

    @property
    def speed_avg(self) -> float:
        return self.speed_sum / self.speed_count if self.speed_count else 0.0

    @property
    def latency_avg(self) -> float:
        return self.latency_sum / self.latency_count if self.latency_count else 0.0

    @property
    def fraud_score(self) -> int:
        """Риск egress-IP 0-100. Приоритет — необработанный риск-скор
        proxycheck.io (fraud_score_raw). Если сервис недоступен —
        оценка по флагам ip-api: +20 mobile, +40 hosting, +70 proxy.
        -1 = данных нет."""
        if self.fraud_score_raw >= 0:
            return self.fraud_score_raw
        if not self.fraud_checked_ts:
            return -1
        score = 0
        if self.fraud_mobile:
            score += 20
        if self.fraud_hosting:
            score += 40
        if self.fraud_proxy:
            score += 70
        return min(100, score)

    @property
    def fraud_verdict(self) -> str:
        s = self.fraud_score
        if s < 0:
            return "UNKNOWN"
        if s < 15:
            return "CLEAN"
        if s < 35:
            return "MOBILE"
        if s < 65:
            return "DC"
        return "PROXY"

    @property
    def fraud_confirmed(self) -> bool:
        """True when fraud data is fresh AND the last attempt confirmed it.

        A refusal (empty result) stamps fraud_attempt_ts, which instantly
        demotes the proxy to unverified even while the previous verdict is
        still inside the freshness window; the next successful check
        restores confirmation because its checked_ts lands after the
        failed attempt."""
        if not self.fraud_checked_ts:
            return False
        if time.time() - self.fraud_checked_ts > self.FRAUD_FRESH_SECONDS:
            return False
        return self.fraud_attempt_ts <= self.fraud_checked_ts

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

    def update_reliability(self, ok: bool):
        """EWMA of check/traffic outcomes; first call seeds from lifetime rate."""
        base = self.sr_ewma if self.sr_ewma >= 0 else (
            self.success_rate if self.checks_total else float(ok))
        a = self.EWMA_ALPHA
        self.sr_ewma = (1.0 - a) * base + a * (1.0 if ok else 0.0)

    def update_latency(self, lat: float):
        a = self.EWMA_ALPHA
        prev = self.latency_ewma
        self.latency_ewma = lat if prev < 0 else (1.0 - a) * prev + a * lat

    def update_speed(self, sp: float):
        a = self.EWMA_ALPHA
        prev = self.speed_ewma
        self.speed_ewma = sp if prev < 0 else (1.0 - a) * prev + a * sp

    def record_traffic_fail(self):
        """Throttled reliability hit from real user-traffic failures."""
        now = time.time()
        if now - self.last_traffic_fail_ts >= self.TRAFFIC_FAIL_THROTTLE:
            self.last_traffic_fail_ts = now
            self.update_reliability(False)

    @property
    def score(self) -> float:
        if self.checks_total == 0:
            return 0.0
        if self.in_blacklist:
            return 0.0
        if self.last_status != "ok":
            # A proven proxy (one that once had non-zero speed) stays ranked
            # during its grace period so it sinks gradually instead of
            # vanishing on the first failure — but deep enough to always rank
            # below any live proxy of comparable quality.
            if not self.in_grace:
                return 0.0
            grace_ratio = max(0.0, 1.0 - self.consecutive_fails / self.GRACE_FAILS)
            return max(0.0, min(100.0, self._base_points() * self._modifier_factor() * 0.3 * grace_ratio))
        return max(0.0, min(100.0, self._base_points() * self._modifier_factor()))

    def _effective_socks(self) -> bool:
        if self.protocol in ("socks4", "socks5"):
            return True
        try:
            return int(self.address.rsplit(":", 1)[1]) in (1080, 10808, 9050, 9051, 4145)
        except (IndexError, ValueError):
            return False

    def _speed_points(self) -> float:
        sp = self.speed_ewma if self.speed_ewma >= 0 else self.speed_avg
        if sp > 0:
            pts = 25.0 * (min(sp, 1600.0) / 1600.0) ** 0.5
            if self.speed_fails > 0:
                pts *= max(0.0, 1.0 - 0.35 * self.speed_fails)
            return pts
        # No usable measurement yet: SOCKS cannot use the HTTP speed servers,
        # a newborn proxy gets provisional credit until its first measurements
        # arrive; a veteran without any measurement evidence scores zero.
        if self._effective_socks():
            return 12.0
        if self.speed_fails == 0 and self.checks_ok < 5:
            return 12.5
        return 0.0

    def _base_points(self) -> float:
        sr = self.sr_ewma if self.sr_ewma >= 0 else self.success_rate
        lat = self.latency_ewma if self.latency_ewma >= 0 else self.latency_avg
        pts = sr * 40.0
        pts += 20.0 * max(0.0, 1.0 - lat / 10.0)
        pts += self._speed_points()
        if self.ssl_supported:
            pts += 5.0
        if self.supports_connect:
            pts += 5.0
        if self._effective_socks():
            pts += 5.0
        return pts

    def _modifier_factor(self) -> float:
        f = 1.0
        if self.fraud_confirmed:
            f *= 1.0 - 0.006 * max(0, self.fraud_score - 15)
        else:
            f *= self.FRAUD_UNKNOWN_FACTOR
        if self.mitm_suspect:
            f *= 0.5
        if self.ip_blacklist_hits > 0:
            f *= max(0.25, 0.75 ** self.ip_blacklist_hits)
        return f

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
            "sr_ewma": round(self.sr_ewma, 4) if self.sr_ewma >= 0 else -1,
            "latency_ewma": round(self.latency_ewma, 4) if self.latency_ewma >= 0 else -1,
            "speed_ewma": round(self.speed_ewma, 4) if self.speed_ewma >= 0 else -1,
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
            "fraud_hosting": self.fraud_hosting,
            "fraud_proxy": self.fraud_proxy,
            "fraud_mobile": self.fraud_mobile,
            "fraud_score_raw": self.fraud_score_raw,
            "fraud_score": self.fraud_score,
            "fraud_verdict": self.fraud_verdict,
            "fraud_checked_ts": self.fraud_checked_ts,
            "fraud_attempt_ts": self.fraud_attempt_ts,
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
            "fraud_hosting": self.fraud_hosting,
            "fraud_proxy": self.fraud_proxy,
            "fraud_mobile": self.fraud_mobile,
            "fraud_score_raw": self.fraud_score_raw,
            "fraud_score": self.fraud_score,
            "fraud_verdict": self.fraud_verdict,
            "fraud_checked_ts": self.fraud_checked_ts,
            "fraud_attempt_ts": self.fraud_attempt_ts,
        }
