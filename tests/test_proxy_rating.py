import pytest
import time
import hunt


class TestProxyRating:
    def test_score_is_zero_for_untested(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080")
        assert r.score == 0.0

    def test_score_is_zero_for_failed(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=0, last_status="failed")
        assert r.score == 0.0

    def test_score_is_zero_for_blacklisted(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=1, last_status="ok")
        r.blacklist_reason = "manual"
        r.in_blacklist = True
        assert r.score == 0.0

    def test_score_is_reduced_for_ip_blacklisted(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=1, last_status="ok")
        r.ip_blacklist_reason = "exit IP blacklisted"
        r.ip_blacklist_hits = 1
        assert r.score > 0.0
        assert r.score < 100.0

    def test_score_decreases_with_more_ip_blacklist_hits(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=1, last_status="ok")
        r.ip_blacklist_reason = "exit IP blacklisted"
        r.ip_blacklist_hits = 1
        score_one = r.score
        r.ip_blacklist_hits = 3
        score_three = r.score
        assert score_one > score_three > 0.0

    def test_score_is_positive_for_ok(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=1, last_status="ok")
        r.latency_sum = 0.5
        r.latency_count = 1
        assert r.score > 0.0

    def test_latency_average(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080")
        r.latency_sum = 1.5
        r.latency_count = 3
        assert r.latency_avg == 0.5

    def test_success_rate(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=4, checks_ok=3)
        assert r.success_rate == 0.75

    def test_to_dict_includes_latency_sum_and_count(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=1, last_status="ok")
        r.latency_sum = 0.6
        r.latency_count = 1
        d = r.to_dict()
        assert d["latency_sum"] == 0.6
        assert d["latency_count"] == 1
        assert d["in_blacklist"] is False

    def test_to_dict_does_not_mark_ip_blacklisted_as_manual_blacklisted(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=1, last_status="ok")
        r.ip_blacklist_reason = "bad exit IP"
        d = r.to_dict()
        # Manual operator blacklist is independent from downloaded IP blacklist.
        assert d["in_blacklist"] is False
        assert d["ip_blacklist_reason"] == "bad exit IP"

    def test_to_dict_marks_manual_blacklisted(self):
        r = hunt.ProxyRating(address="1.2.3.4:8080", checks_total=1, checks_ok=1, last_status="ok")
        r.in_blacklist = True
        r.blacklist_reason = "manual"
        d = r.to_dict()
        assert d["in_blacklist"] is True
        assert d["blacklist_reason"] == "manual"
