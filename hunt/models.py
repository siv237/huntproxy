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
    # A fraud reading older than this no longer counts as fresh; while
    # there is no fresh reading the proxy sits in FAILCHECK (worst case,
    # marked — see fraud_failcheck).
    FRAUD_FRESH_SECONDS = 6 * 3600.0
    # Fraud moves the base rating sharply in BOTH directions. The reading
    # comes from ip-api egress flags captured during the regular scan
    # (wiki: 0 = CLEAN resident, hosting -> DC, proxy -> PROXY):
    #   multiplier = 1 - PER_POINT * (score - BOOST_CENTER), clamped.
    # A clean resident exit raises the base (~x1.3 at 0), a flagged one
    # sinks it (x0.9 at 40, x0.6 at 70, x0.3 at 100). Flags are captured
    # on every pass of every candidate — no separate probe needed.
    # proxycheck.io raw risk (when present) is informational only: it
    # answers "is this IP a proxy" (always true here), not "how dirty
    # is the network behind it".
    FRAUD_PENALTY_PER_POINT = 0.01
    FRAUD_BOOST_CENTER = 30
    FRAUD_FACTOR_MIN = 0.10
    FRAUD_FACTOR_MAX = 1.35
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
    fraud_raw_ts: float = 0.0  # когда был получен именно raw-скор proxycheck
    fraud_attempt_ts: float = 0.0  # когда последняя попытка проверки не дала данных (диагностика)
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
        """Точный риск 0-100 из свежего чтения флагов ip-api
        (0 CLEAN / +20 mobile / +40 hosting / +70 proxy); пока чтения нет —
        100 (худший случай), отличать от реального readings помогает
        fraud_failcheck."""
        if self.fraud_failcheck:
            return 100
        score = 0
        if self.fraud_mobile:
            score += 20
        if self.fraud_hosting:
            score += 40
        if self.fraud_proxy:
            score += 70
        return min(100, score)

    @property
    def fraud_failcheck(self) -> bool:
        """True when the worst-case default is in effect because the egress
        flags have never been captured or went stale (failed scan). The 100
        shown by fraud_score is a placeholder — UI renders FAILCHECK/FC."""
        if not self.fraud_checked_ts:
            return True
        return time.time() - self.fraud_checked_ts > self.FRAUD_FRESH_SECONDS

    @property
    def fraud_verified(self) -> bool:
        return not self.fraud_failcheck

    @property
    def fraud_verdict(self) -> str:
        if self.fraud_failcheck:
            return "FAILCHECK"
        s = self.fraud_score
        if s < 15:
            return "CLEAN"
        if s < 35:
            return "MOBILE"
        if s < 65:
            return "DC"
        return "PROXY"

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
        """Throttled reliability hit from real user-traffic failures.

        The throttle covers the whole penalty — consecutive_fails included:
        a burst of connection errors within one page load is one failure,
        not dozens, so a brief outage cannot instantly burn a proven
        proxy's grace period."""
        now = time.time()
        if now - self.last_traffic_fail_ts >= self.TRAFFIC_FAIL_THROTTLE:
            self.last_traffic_fail_ts = now
            self.consecutive_fails += 1
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
        f = 1.0 - self.FRAUD_PENALTY_PER_POINT * (self.fraud_score - self.FRAUD_BOOST_CENTER)
        f = max(self.FRAUD_FACTOR_MIN, min(self.FRAUD_FACTOR_MAX, f))
        if self.mitm_suspect:
            f *= 0.5
        if self.ip_blacklist_hits > 0:
            f *= max(0.25, 0.75 ** self.ip_blacklist_hits)
        return f

    def score_breakdown(self) -> dict:
        """Authoritative score decomposition for UI: base components,
        multipliers and the exact formula — mirrors score()/helpers."""
        sr = self.sr_ewma if self.sr_ewma >= 0 else (
            self.success_rate if self.checks_total else 0.0)
        lat = self.latency_ewma if self.latency_ewma >= 0 else self.latency_avg
        sp = self.speed_ewma if self.speed_ewma >= 0 else self.speed_avg
        if sp > 0:
            speed_pts = 25.0 * (min(sp, 1600.0) / 1600.0) ** 0.5
            if self.speed_fails > 0:
                speed_pts *= max(0.0, 1.0 - 0.35 * self.speed_fails)
        elif self._effective_socks():
            speed_pts = 12.0
        elif self.speed_fails == 0 and self.checks_ok < 5:
            speed_pts = 12.5
        else:
            speed_pts = 0.0
        base = [
            {"key": "reliability", "value": round(sr * 40.0, 1), "max": 40},
            {"key": "latency", "value": round(20.0 * max(0.0, 1.0 - lat / 10.0), 1), "max": 20},
            {"key": "speed", "value": round(speed_pts, 1), "max": 25},
            {"key": "ssl", "value": 5.0 if self.ssl_supported else 0.0, "max": 5},
            {"key": "connect", "value": 5.0 if self.supports_connect else 0.0, "max": 5},
            {"key": "socks", "value": 5.0 if self._effective_socks() else 0.0, "max": 5},
        ]
        base_sum = round(sum(row["value"] for row in base), 1)

        f_fraud = 1.0 - self.FRAUD_PENALTY_PER_POINT * (self.fraud_score - self.FRAUD_BOOST_CENTER)
        f_fraud = max(self.FRAUD_FACTOR_MIN, min(self.FRAUD_FACTOR_MAX, f_fraud))
        if self.fraud_failcheck:
            fraud_note = "FAILCHECK"
        else:
            fraud_note = f"{self.fraud_verdict} {self.fraud_score}"
        mults = [
            {"key": "fraud", "factor": round(f_fraud, 2), "note": fraud_note},
            {"key": "mitm", "factor": 0.5 if self.mitm_suspect else 1.0,
             "note": "" },
            {"key": "ipbl", "factor": round(max(0.25, 0.75 ** self.ip_blacklist_hits), 2)
             if self.ip_blacklist_hits else 1.0,
             "note": f"{self.ip_blacklist_hits}x" if self.ip_blacklist_hits else ""},
        ]
        if self.last_status != "ok" and self.in_grace:
            ratio = max(0.0, 1.0 - self.consecutive_fails / self.GRACE_FAILS)
            mults.append({"key": "grace", "factor": round(0.3 * ratio, 2),
                          "note": f"{self.consecutive_fails}"})
        return {"base": base, "base_sum": base_sum,
                "multipliers": mults, "final": round(self.score, 1)}

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
            "fraud_failcheck": self.fraud_failcheck,
            "fraud_checked_ts": self.fraud_checked_ts,
            "fraud_raw_ts": self.fraud_raw_ts,
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
            "fraud_failcheck": self.fraud_failcheck,
            "fraud_checked_ts": self.fraud_checked_ts,
            "fraud_raw_ts": self.fraud_raw_ts,
            "fraud_attempt_ts": self.fraud_attempt_ts,
        }
