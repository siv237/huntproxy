import pytest
import hunt


class TestIpBlacklist:
    def test_parse_exact_ip(self, state):
        text = "1.2.3.4\n5.6.7.8\n"
        count = state._parse_ip_blacklist(text, "test", "Test Source")
        assert count == 2
        assert "1.2.3.4" in state.ip_blacklist_exact
        assert state._is_ip_blacklisted("1.2.3.4")[0] is True

    def test_parse_cidr(self, state):
        text = "192.168.0.0/16\n"
        state._parse_ip_blacklist(text, "test", "Test Source")
        assert state._is_ip_blacklisted("192.168.1.1")[0] is True
        assert state._is_ip_blacklisted("10.0.0.1")[0] is False

    def test_parse_ip_range(self, state):
        text = "10.0.0.1-10.0.0.5\n"
        state._parse_ip_blacklist(text, "test", "Test Source")
        assert state._is_ip_blacklisted("10.0.0.3")[0] is True
        assert state._is_ip_blacklisted("10.0.0.6")[0] is False

    def test_parse_ignores_comments_and_empty_lines(self, state):
        text = "# comment\n\n1.2.3.4\n! bad line\n"
        count = state._parse_ip_blacklist(text, "test", "Test Source")
        assert count == 1

    def test_parse_ignores_invalid_tokens(self, state):
        text = "not-an-ip\n1.2.3.4\n"
        count = state._parse_ip_blacklist(text, "test", "Test Source")
        assert count == 1

    def test_parse_netset_with_comments(self, state):
        text = "# Firehol list\n1.2.3.4\n192.168.0.0/16\n"
        count = state._parse_ip_blacklist(text, "firehol", "FireHOL")
        assert count == 2

    def test_reason_includes_source_name(self, state):
        text = "1.2.3.4\n"
        state._parse_ip_blacklist(text, "test", "Test Source")
        _, reason = state._is_ip_blacklisted("1.2.3.4")
        assert "Test Source" in reason

    def test_ipv6_support(self, state):
        text = "2001:db8::/32\n"
        state._parse_ip_blacklist(text, "test", "Test Source")
        assert state._is_ip_blacklisted("2001:db8::1")[0] is True
        assert state._is_ip_blacklisted("2001:db9::1")[0] is False

    def test_apply_ip_blacklist_to_proxy_sets_reason(self, state):
        text = "8.8.8.8\n"
        state._parse_ip_blacklist(text, "test", "Test Source")
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=1, checks_ok=1)
        r.egress_ip = "8.8.8.8"
        state.ratings["1.2.3.4:8080"] = r
        state._apply_ip_blacklist_to_proxy("1.2.3.4:8080", "8.8.8.8")
        assert r.ip_blacklist_reason == "blacklist from Test Source"
        assert r.is_blacklisted is True

    def test_apply_ip_blacklist_to_proxy_clears_when_removed(self, state):
        text = "8.8.8.8\n"
        state._parse_ip_blacklist(text, "test", "Test Source")
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=1, checks_ok=1)
        r.egress_ip = "8.8.8.8"
        r.ip_blacklist_reason = "old reason"
        state.ratings["1.2.3.4:8080"] = r
        state.ip_blacklist_entries.clear()
        state.ip_blacklist_exact.clear()
        state._apply_ip_blacklist_to_proxy("1.2.3.4:8080", "8.8.8.8")
        assert r.ip_blacklist_reason == ""
