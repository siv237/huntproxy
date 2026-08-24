import time

import pytest

import hunt
from hunt.proxy_routing import ProxyRouteMixin


def _resident(address=None, **kw):
    """Healthy proxy: sr 0.95, 0.8s latency, 600 KB/s, SSL+CONNECT."""
    if address is None:
        address = kw.pop("address", "1.2.3.4:8080")
    fields = dict(checks_total=20, checks_ok=19, last_status="ok",
                  ssl_supported=True, supports_connect=True, speed_count=1)
    fields.update(kw)
    r = hunt.ProxyRating(address=address, **fields)
    r.sr_ewma = 0.95
    r.latency_ewma = 0.8
    r.speed_ewma = 600.0
    return r


class TestScoreMatrix:
    def test_fresh_clean_resident_profile(self):
        r = _resident()
        assert abs(r.score - 81.7) < 1.5

    def test_dc_risk_45_dampened_but_solid(self):
        r = _resident(fraud_score_raw=45, fraud_checked_ts=time.time())
        base = _resident().score
        expected = base * (1.0 - 0.006 * (45 - 15))
        assert abs(r.score - expected) < 0.01
        assert 60 < r.score < base

    def test_flagged_vpn_risk_90_halved(self):
        clean = _resident().score
        r = _resident(fraud_score_raw=90, fraud_checked_ts=time.time())
        assert abs(r.score - clean * (1.0 - 0.006 * 75)) < 0.01
        assert r.score < clean * 0.6

    def test_stale_fraud_data_is_neutral(self):
        r = _resident(fraud_score_raw=95)
        r.fraud_checked_ts = time.time() - hunt.ProxyRating.FRAUD_FRESH_SECONDS - 1
        assert r.score == _resident().score

    def test_mitm_multiplies_not_subtracts(self):
        strong = _resident()
        weak = _resident(address="1.2.3.4:8081")
        weak.sr_ewma = 0.4
        weak.speed_ewma = 100.0
        strong_mitm = strong.score * 0.5
        weak_mitm = weak.score * 0.5
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
        r = hunt.ProxyRating(address="1.2.3.4:1080", protocol="socks5",
                             checks_total=10, checks_ok=9, last_status="ok")
        r.sr_ewma = 0.9
        r.latency_ewma = 1.0
        assert r._speed_points() == 12.0
        http_twin = hunt.ProxyRating(address="1.2.3.4:8080",
                                     checks_total=10, checks_ok=9, last_status="ok")
        http_twin.sr_ewma = 0.9
        http_twin.latency_ewma = 1.0
        assert r.score - http_twin.score == pytest.approx(17.0)

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
