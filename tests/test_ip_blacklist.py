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
        _, sources = state._is_ip_blacklisted("1.2.3.4")
        assert any("Test Source" in s.get("source_name", "") for s in sources)

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

    def test_multiple_sources_increase_ip_blacklist_hits(self, state):
        state._parse_ip_blacklist("8.8.8.8\n", "src1", "Source 1")
        state._parse_ip_blacklist("8.8.8.8\n", "src2", "Source 2")
        r = hunt.ProxyRating(address="1.2.3.4:8080", last_status="ok", checks_total=1, checks_ok=1)
        r.egress_ip = "8.8.8.8"
        state.ratings["1.2.3.4:8080"] = r
        state._apply_ip_blacklist_to_proxy("1.2.3.4:8080", "8.8.8.8")
        assert r.ip_blacklist_hits == 2
        assert len(r.ip_blacklist_sources) == 2
        assert "Source 1" in r.ip_blacklist_reason
        assert "Source 2" in r.ip_blacklist_reason

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

    def test_persist_ip_blacklist_source(self, state):
        text = "1.2.3.4\n5.6.7.8\n"
        count = state._parse_ip_blacklist(text, "src1", "Source 1", persist=True)
        assert count == 2
        conn = state._db()
        rows = conn.execute("SELECT entry FROM ip_blacklist_entries WHERE source_id='src1'").fetchall()
        conn.close()
        assert {r["entry"] for r in rows} == {"1.2.3.4", "5.6.7.8"}

    def test_ip_blacklist_reloads_from_db(self, state):
        state._parse_ip_blacklist("1.2.3.4\n", "src1", "Source 1", persist=True)
        state.ip_blacklist_entries.clear()
        state.ip_blacklist_exact.clear()
        state.ip_blacklist_networks.clear()
        state._load_ip_blacklist_from_db(accumulate=False)
        assert state._is_ip_blacklisted("1.2.3.4")[0] is True

    def test_replace_source_updates_only_that_source(self, state):
        state._parse_ip_blacklist("1.2.3.4\n", "src1", "Source 1", persist=True)
        state._parse_ip_blacklist("1.2.3.4\n5.6.7.8\n", "src2", "Source 2", persist=True)
        conn = state._db()
        rows = conn.execute("SELECT source_id, entry FROM ip_blacklist_entries").fetchall()
        conn.close()
        pairs = {(r["source_id"], r["entry"]) for r in rows}
        assert ("src1", "1.2.3.4") in pairs
        assert ("src2", "1.2.3.4") in pairs
        assert ("src2", "5.6.7.8") in pairs
        # Replace src1 with a different entry; src2 should remain untouched.
        state._replace_ip_blacklist_source("src1", "Source 1", [("5.6.7.8", "reason")])
        conn = state._db()
        rows = conn.execute("SELECT source_id, entry FROM ip_blacklist_entries").fetchall()
        conn.close()
        pairs = {(r["source_id"], r["entry"]) for r in rows}
        assert ("src1", "5.6.7.8") in pairs
        assert ("src2", "1.2.3.4") in pairs
        assert ("src2", "5.6.7.8") in pairs
        assert ("src1", "1.2.3.4") not in pairs

    def test_delete_ip_blacklist_source_removes_entries(self, state):
        state.create_ip_blacklist_source({"id": "src-api", "name": "API Source", "url": "http://example.com/bl.txt"})
        state._parse_ip_blacklist("1.2.3.4\n", "src-api", "API Source", persist=True)
        assert state._is_ip_blacklisted("1.2.3.4")[0] is True
        state.delete_ip_blacklist_source("src-api")
        assert state._is_ip_blacklisted("1.2.3.4")[0] is False
        conn = state._db()
        count = conn.execute("SELECT COUNT(*) as c FROM ip_blacklist_entries WHERE source_id='src-api'").fetchone()["c"]
        conn.close()
        assert count == 0

    def test_toggle_disable_clears_ip_blacklist_entries(self, state):
        state.create_ip_blacklist_source({"id": "src-toggle", "name": "Toggle Source", "url": "http://example.com/bl.txt"})
        state._parse_ip_blacklist("1.2.3.4\n", "src-toggle", "Toggle Source", persist=True)
        assert state._is_ip_blacklisted("1.2.3.4")[0] is True
        state.toggle_ip_blacklist_source("src-toggle")
        assert state._is_ip_blacklisted("1.2.3.4")[0] is False
        # Re-enabling the source leaves it empty until the next fetch.
        result = state.toggle_ip_blacklist_source("src-toggle")
        assert result is not None
        assert result["enabled"] == 1

    def test_update_disable_clears_ip_blacklist_entries(self, state):
        state.create_ip_blacklist_source({"id": "src-update", "name": "Update Source", "url": "http://example.com/bl.txt"})
        state._parse_ip_blacklist("1.2.3.4\n", "src-update", "Update Source", persist=True)
        assert state._is_ip_blacklisted("1.2.3.4")[0] is True
        state.update_ip_blacklist_source("src-update", {"enabled": False})
        assert state._is_ip_blacklisted("1.2.3.4")[0] is False
        conn = state._db()
        count = conn.execute("SELECT COUNT(*) as c FROM ip_blacklist_entries WHERE source_id='src-update'").fetchone()["c"]
        conn.close()
        assert count == 0
