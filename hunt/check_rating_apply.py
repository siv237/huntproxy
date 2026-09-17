"""Rating-result application helpers — extracted from check_rating.py."""

import time

from hunt.geo import country_code_from_name
from hunt.models import ProxyRating


class CheckRatingApplyMixin:
    def _apply_ok_result(self, r: ProxyRating, country: str, country_code: str,
                         latency: float, speed: float, supports_connect: bool,
                         ssl_supported: bool, mitm_suspect: bool,
                         egress: dict, listen: dict, fraud: dict):
        r.checks_ok += 1
        r.latency_sum += latency
        r.latency_count += 1
        r.last_status = "ok"
        r.last_ok = time.time()
        r.consecutive_fails = 0
        self._apply_speed(r, speed)
        if speed > 0:
            r.update_speed(speed)
        r.update_latency(latency)
        self._apply_country(r, country, country_code)
        r.supports_connect = supports_connect
        r.ssl_supported = ssl_supported
        if ssl_supported and r.protocol not in ('socks5', 'socks4'):
            r.protocol = 'https'
        r.mitm_suspect = bool(mitm_suspect)
        if egress:
            self._apply_egress(r, egress)
        if listen:
            self._apply_listen(r, listen)
        if fraud:
            self._apply_fraud(r, fraud)
        elif fraud is not None:
            # The fraud probe ran but produced nothing (refused, quota,
            # timeout). Stamp the attempt for diagnostics; scoring already
            # treats the proxy as unverified via the fail-closed default.
            r.fraud_attempt_ts = time.time()

    def _apply_fraud(self, r: ProxyRating, fraud: dict):
        """Store the raw proxycheck.io risk score as INFORMATION ONLY.

        proxycheck answers "is this IP a proxy" (always yes here), not
        "how dirty is the network behind it" — it must never write into
        the ip-api flag fields that drive fraud_score."""
        score = fraud.get("score")
        if isinstance(score, int) and 0 <= score <= 100:
            r.fraud_score_raw = score
            now = time.time()
            r.fraud_checked_ts = now
            r.fraud_raw_ts = now

    def _apply_speed(self, r: ProxyRating, speed: float):
        if speed > 0:
            r.speed_sum += speed
            r.speed_count += 1
            r.last_speed = speed
            r.speed_fails = 0
        else:
            r.speed_fails += 1

    def _apply_country(self, r: ProxyRating, country: str, country_code: str):
        if country and (not r.country or len(country) > len(r.country)):
            r.country = country
        if country_code and not r.country_code:
            r.country_code = country_code
        elif country and not r.country_code:
            r.country_code = country_code_from_name(country)
        elif country and r.country and country != r.country:
            derived = country_code_from_name(country)
            if derived:
                r.country_code = derived

    def _apply_egress(self, r: ProxyRating, egress: dict):
        r.egress_ip = egress.get("egress_ip") or r.egress_ip
        r.egress_city = egress.get("egress_city") or r.egress_city
        r.egress_isp = egress.get("egress_isp") or r.egress_isp
        new_country = egress.get("egress_country")
        if new_country:
            # The name is overwritten on every check, but the code was only
            # derived when empty — a proxy that hopped countries (Chile →
            # United States) kept the stale code forever and the UI showed
            # the wrong flag.  Re-derive whenever the name actually changed.
            if new_country != r.egress_country or not r.egress_country_code:
                code = country_code_from_name(new_country)
                if code:
                    r.egress_country_code = code
            r.egress_country = new_country
        if "egress_hosting" in egress or "egress_proxy" in egress:
            r.fraud_hosting = bool(egress.get("egress_hosting"))
            r.fraud_proxy = bool(egress.get("egress_proxy"))
            r.fraud_mobile = bool(egress.get("egress_mobile"))
            r.fraud_checked_ts = time.time()

    def _apply_listen(self, r: ProxyRating, listen: dict):
        new_country = listen.get("country")
        if new_country:
            if new_country != r.listen_country or not r.listen_country_code:
                code = country_code_from_name(new_country)
                if code:
                    r.listen_country_code = code
            r.listen_country = new_country
        r.listen_city = listen.get("city") or r.listen_city
        r.listen_isp = listen.get("isp") or r.listen_isp
