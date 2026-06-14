import hunt


class TestBlacklist:
    def test_blacklist_add_and_remove(self, state):
        addr = "1.2.3.4:8080"
        state.ratings[addr] = hunt.ProxyRating(address=addr)
        state.blacklist_add(addr, "test reason")
        assert addr in state.blacklist
        assert state.blacklist[addr] == "test reason"
        assert state.ratings[addr].in_blacklist is True
        assert state.ratings[addr].blacklist_reason == "test reason"

        state.blacklist_remove(addr)
        assert addr not in state.blacklist
        assert state.ratings[addr].in_blacklist is False
        assert state.ratings[addr].blacklist_reason == ""

    def test_blacklist_add_without_reason(self, state):
        addr = "1.2.3.4:8080"
        state.blacklist_add(addr)
        assert state.blacklist[addr] == "manual"

    def test_blacklist_remove_unknown_address(self, state):
        # should not raise
        state.blacklist_remove("9.9.9.9:9999")

    def test_blacklist_view(self, state):
        state.blacklist_add("1.2.3.4:8080", "reason1")
        state.blacklist_add("5.6.7.8:3128", "reason2")
        view = state._blacklist_view()
        addresses = {item["address"] for item in view}
        assert addresses == {"1.2.3.4:8080", "5.6.7.8:3128"}

    def test_blacklist_score_zero(self, state):
        addr = "1.2.3.4:8080"
        r = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1, checks_ok=1)
        state.ratings[addr] = r
        state.blacklist_add(addr)
        assert r.score == 0.0
        assert r.is_blacklisted is True

    def test_snapshot_counts_blacklist(self, state):
        state.blacklist_add("1.2.3.4:8080")
        snapshot = state.get_snapshot()
        assert snapshot["counts"]["blacklist"] >= 1
