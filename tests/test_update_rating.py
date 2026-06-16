import hunt
import time


class TestUpdateRating:
    def test_update_rating_increments_latency_sum_and_count(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080",
            ok=True,
            country="US",
            latency=0.5,
            supports_connect=False,
            mitm_suspect=False,
            egress={},
            listen={},
            speed=100.0,
            country_code="US",
            ssl_supported=False,
        )
        r = state.ratings["1.2.3.4:8080"]
        assert r.checks_total == 1
        assert r.checks_ok == 1
        assert r.latency_sum == 0.5
        assert r.latency_count == 1
        assert r.latency_avg == 0.5
        assert r.last_latency == 0.5
        assert r.speed_sum == 100.0
        assert r.speed_count == 1
        assert r.speed_avg == 100.0

    def test_update_rating_does_not_increment_speed_on_zero(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080",
            ok=True,
            country="US",
            latency=0.5,
            speed=0.0,
        )
        r = state.ratings["1.2.3.4:8080"]
        assert r.speed_count == 0
        assert r.speed_fails == 1

    def test_update_rating_marks_failed(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:8080",
            ok=False,
            country="US",
            latency=0.0,
        )
        r = state.ratings["1.2.3.4:8080"]
        assert r.last_status == "failed"
        assert r.checks_total == 1
        assert r.checks_ok == 0
        assert r.latency_count == 0

    def test_update_rating_applies_ip_blacklist(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._parse_ip_blacklist("8.8.8.8\n", "test", "Test")
        state._update_rating(
            "1.2.3.4:8080",
            ok=True,
            country="US",
            latency=0.5,
            egress={"egress_ip": "8.8.8.8"},
        )
        r = state.ratings["1.2.3.4:8080"]
        assert r.ip_blacklist_reason != ""
        assert r.is_blacklisted is True
        assert r.ip_blacklist_hits == 1
        # IP-blacklist is no longer a hard sentence; score is reduced but positive.
        assert r.score > 0.0

    def test_update_rating_accumulates_multiple_checks(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        for latency in [0.5, 0.7, 0.6]:
            state._update_rating(
                "1.2.3.4:8080",
                ok=True,
                country="US",
                latency=latency,
                speed=100.0,
            )
        r = state.ratings["1.2.3.4:8080"]
        assert r.checks_total == 3
        assert r.checks_ok == 3
        assert r.latency_count == 3
        assert abs(r.latency_avg - 0.6) < 0.001
        assert r.speed_count == 3
        assert r.speed_avg == 100.0

    def test_update_rating_updates_existing_proxy(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        r = hunt.ProxyRating(address="1.2.3.4:8080")
        r.checks_total = 5
        r.checks_ok = 5
        r.latency_sum = 3.0
        r.latency_count = 5
        r.last_status = "ok"
        state.ratings["1.2.3.4:8080"] = r
        state._update_rating(
            "1.2.3.4:8080",
            ok=True,
            country="US",
            latency=0.5,
        )
        assert r.checks_total == 6
        assert r.latency_count == 6
        assert r.latency_sum == 3.5

    def test_update_rating_sets_https_protocol_for_ssl_proxy(self, tmp_data_dir):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state._update_rating(
            "1.2.3.4:443",
            ok=True,
            country="US",
            latency=0.5,
            ssl_supported=True,
        )
        r = state.ratings["1.2.3.4:443"]
        assert r.protocol == "https"
        assert r.ssl_supported is True
