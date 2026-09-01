import time

import pytest

import hunt
from hunt.proxy_routing import ProxyRouteMixin


def _resident(address=None, **kw):
    """Healthy proxy: sr 0.95, 0.8s latency, 600 KB/s, SSL+CONNECT,
    fresh fraud reading (default: clean resident exit, score 0 -> x1.3)."""
    if address is None:
        address = kw.pop("address", "1.2.3.4:8080")
    fields = dict(checks_total=20, checks_ok=19, last_status="ok",
                  ssl_supported=True, supports_connect=True, speed_count=1,
                  fraud_checked_ts=time.time())
    fields.update(kw)
    r = hunt.ProxyRating(address=address, **fields)
    r.sr_ewma = 0.95
    r.latency_ewma = 0.8
    r.speed_ewma = 600.0
    return r


_CLEAN_FACTOR = 1.0 - hunt.ProxyRating.FRAUD_PENALTY_PER_POINT * (0 - 30)


class TestScoreMatrix:
    def test_fresh_clean_resident_caps_at_100(self):
        r = _resident()
        assert not r.fraud_failcheck
        assert r.fraud_score == 0
        bp = r._base_points()
        assert r.score == pytest.approx(min(100.0, bp * _CLEAN_FACTOR))

    def test_dc_hosting_dampened_but_solid(self):
        r = _resident(fraud_hosting=True)
        bp = r._base_points()
        expected = max(0.0, min(100.0, bp * (1.0 - 0.01 * (40 - 30))))
        assert r.score == pytest.approx(expected)
        assert 55 < r.score < _resident().score

    def test_flagged_vpn_sharply_sunk(self):
        clean = _resident().score
        r = _resident(fraud_proxy=True)
        bp = r._base_points()
        assert r.score == pytest.approx(bp * (1.0 - 0.01 * 40))
        assert r.score < clean * 0.5

    def test_failcheck_is_worst_case_but_marked(self):
        stale = time.time() - hunt.ProxyRating.FRAUD_FRESH_SECONDS - 1
        r = _resident(fraud_proxy=True, fraud_checked_ts=stale)
        assert not r.fraud_verified
        assert r.fraud_failcheck
        assert r.fraud_score == 100
        assert r.fraud_verdict == "FAILCHECK"
        bp = r._base_points()
        assert r.score == pytest.approx(bp * (1.0 - 0.01 * 70))

    def test_mitm_multiplies_not_subtracts(self):
        strong = _resident()
        weak = _resident(address="1.2.3.4:8081")
        weak.sr_ewma = 0.4
        weak.speed_ewma = 100.0
        # cap applies to the FINAL product, not the base:
        # expected = base_points * speed_factor * clean_factor * mitm_penalty
        strong_mitm = min(100.0, strong._base_points() * strong._speed_factor() * _CLEAN_FACTOR * 0.5)
        weak_mitm = min(100.0, weak._base_points() * weak._speed_factor() * _CLEAN_FACTOR * 0.5)
        strong.mitm_suspect = True
        weak.mitm_suspect = True
        assert strong.score == pytest.approx(strong_mitm)
        assert weak.score == pytest.approx(weak_mitm)
        # multiplicative: strong-mitm still above weak-mitm
        assert strong.score > weak.score

    def test_grace_corpse_below_any_live_proxy(self):
        corpse = _resident(last_status="failed")
        corpse.consecutive_fails = 2
        mediocre = _resident(address="1.2.3.4:8081")
        mediocre.sr_ewma = 0.55
        mediocre.speed_ewma = 120.0
        assert corpse.score < mediocre.score
        assert corpse.score < _resident().score * 0.35


class TestFraudVerification:
    def test_verified_clean_beats_failcheck_twin(self):
        verified = _resident()
        failcheck = _resident(address="1.2.3.4:8081",
                              fraud_checked_ts=0.0)
        assert failcheck.fraud_failcheck
        assert verified.score > failcheck.score
        bp = verified._base_points()
        assert failcheck.score == pytest.approx(bp * (1.0 - 0.01 * 70))

    def test_monotonic_ladder_clean_accused_failcheck(self):
        clean = _resident().score
        accused = _resident(fraud_proxy=True).score
        failcheck = _resident(address="1.2.3.4:8083",
                              fraud_checked_ts=0.0).score
        assert clean > accused > failcheck

    def test_scan_without_egress_keeps_fresh_reading(self):
        r = _resident()
        base = r.score
        assert not r.fraud_failcheck
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state.ratings[r.address] = r
        state._update_rating(r.address, ok=True, country="US", latency=0.6,
                             speed=600.0, supports_connect=True,
                             ssl_supported=True)
        assert not r.fraud_failcheck
        assert r.score == pytest.approx(base, abs=2.0)

    def test_expiry_demotes_until_rescan(self):
        stale = time.time() - hunt.ProxyRating.FRAUD_FRESH_SECONDS - 1
        r = _resident(fraud_checked_ts=stale)
        assert r.fraud_failcheck
        sunk = r.score
        r.fraud_checked_ts = time.time()
        assert not r.fraud_failcheck
        assert r.score > sunk

    def test_failcheck_ranks_below_measured_accusation(self):
        failcheck = _resident(address="1.2.3.4:8081",
                              fraud_checked_ts=0.0)
        flagged = _resident(fraud_hosting=True)
        assert failcheck.score < flagged.score

    def test_update_rating_stamps_attempt_on_empty_probe(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        addr = "1.2.3.4:8080"
        state._update_rating(addr, ok=True, country="US", latency=0.5,
                             fraud={"provider": "proxycheck", "score": 5})
        r = state.ratings[addr]
        checked = r.fraud_checked_ts
        assert r.fraud_verified
        state._update_rating(addr, ok=True, country="US", latency=0.5, fraud={})
        assert r.fraud_attempt_ts >= checked


class TestEwma:
    def test_reliability_seeds_from_lifetime(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080",
                             checks_total=10, checks_ok=8, last_status="ok")
        r.update_reliability(True)
        assert r.sr_ewma == pytest.approx(0.8 * 0.75 + 0.25)

    def test_old_legend_sinks_after_fail_window(self):
        legend = _resident()
        legend.sr_ewma = 0.98
        rookie = _resident(address="1.2.3.4:8081")
        rookie.sr_ewma = 0.75
        for _ in range(12):
            legend.update_reliability(False)
            rookie.update_reliability(False)
            legend.update_reliability(True)
            rookie.update_reliability(True)
        # both recover, but legend's lifetime advantage is forgotten
        assert abs(legend.sr_ewma - rookie.sr_ewma) < 0.05

    def test_latency_and_speed_ewma_track_changes(self):
        r = _resident()
        old_lat = r.latency_ewma
        for _ in range(10):
            r.update_latency(5.0)
        assert r.latency_ewma > old_lat
        assert r.latency_ewma < 5.0
        old_sp = r.speed_ewma
        for _ in range(10):
            r.update_speed(1200.0)
        assert r.speed_ewma > old_sp

    def test_traffic_fail_updates_reliability_throttled(self):
        r = _resident()
        before = r.sr_ewma
        r.record_traffic_fail()
        after_first = r.sr_ewma
        assert after_first < before
        for _ in range(5):
            r.record_traffic_fail()
        assert r.sr_ewma == pytest.approx(after_first)
        r.last_traffic_fail_ts -= hunt.ProxyRating.TRAFFIC_FAIL_THROTTLE + 0.01
        r.record_traffic_fail()
        assert r.sr_ewma < after_first


class TestSpeedPointsV2:
    def test_newborn_gets_provisional_credit(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080",
                             checks_total=2, checks_ok=2, last_status="ok")
        assert r._speed_points() == 12.5
        assert r.score > 0.0

    def test_veteran_without_any_speed_scores_zero_speed(self):
        r = _resident(speed_count=0)
        r.speed_ewma = -1.0
        r.checks_ok = 9
        assert r._speed_points() == 0.0

    def test_socks_fixed_speed_credit_and_feature_bonus(self):
        now = time.time()
        r = hunt.ProxyRating(address="1.2.3.4:1080", protocol="socks5",
                             checks_total=10, checks_ok=9, last_status="ok",
                             fraud_checked_ts=now,
                             fraud_hosting=True)
        r.sr_ewma = 0.9
        r.latency_ewma = 1.0
        # SOCKS cannot use the HTTP speed servers: it gets a provisional
        # speed factor even with no measurement (HTTP twin with no speed -> 0).
        assert r._speed_factor() == hunt.ProxyRating.SPEED_NEWBORN_FACTOR
        http_twin = hunt.ProxyRating(address="1.2.3.4:8080",
                                     checks_total=10, checks_ok=9, last_status="ok",
                                     fraud_checked_ts=now,
                                     fraud_hosting=True)
        http_twin.sr_ewma = 0.9
        http_twin.latency_ewma = 1.0
        # DC-flag multiplier (score 40 -> x0.9) scales the whole product.
        expected = (r._base_points() * r._speed_factor() * r._modifier_factor()
                    - http_twin._base_points() * http_twin._speed_factor() * http_twin._modifier_factor())
        assert r.score - http_twin.score == pytest.approx(expected)

    def test_speed_saturation_log_like(self):
        low = hunt.ProxyRating(address="1.2.3.4:8080")
        low.speed_ewma = 400.0
        high = hunt.ProxyRating(address="1.2.3.4:8080")
        high.speed_ewma = 1600.0
        huge = hunt.ProxyRating(address="1.2.3.4:8080")
        huge.speed_ewma = 6000.0
        assert high._speed_points() == pytest.approx(25.0)
        assert huge._speed_points() == pytest.approx(25.0)
        assert low._speed_points() < 15.0


class TestPoolPartition:
    def _state_with_pool(self):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        ok_strong = _resident("9.9.9.1:8080")
        ok_weak = _resident("9.9.9.2:8080")
        ok_weak.sr_ewma = 0.05
        ok_weak.latency_ewma = 3.0
        ok_weak.ssl_supported = False
        ok_weak.supports_connect = False
        ok_weak.speed_ewma = 60.0
        grace_strong = _resident("9.9.9.3:8080", last_status="failed")
        grace_strong.consecutive_fails = 1
        state.ratings = {r.address: r for r in (grace_strong, ok_weak, ok_strong)}
        return state, [ok_strong, ok_weak], grace_strong

    def test_live_proxies_precede_grace_even_when_grace_outscores(self):
        state, live, corpse = self._state_with_pool()
        assert corpse.score > live[1].score
        mixin = ProxyRouteMixin.__new__(ProxyRouteMixin)
        mixin.state = state
        pool = mixin._build_pool(need_connect=False)
        addrs = [r.address for r in pool]
        assert addrs.index(live[0].address) < addrs.index(corpse.address)
        assert addrs[-1] == corpse.address

    def test_blacklisted_never_in_pool(self):
        state, live, corpse = self._state_with_pool()
        live[0].in_blacklist = True
        mixin = ProxyRouteMixin.__new__(ProxyRouteMixin)
        mixin.state = state
        pool = mixin._build_pool(need_connect=False)
        assert live[0].address not in [r.address for r in pool]
