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

    def test_blacklist_remove_keeps_ip_blacklist(self, state):
        addr = "1.2.3.4:8080"
        r = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1, checks_ok=1)
        r.egress_ip = "8.8.8.8"
        state.ratings[addr] = r
        state._parse_ip_blacklist("8.8.8.8\n", "test", "Test Source")
        state._apply_ip_blacklist_to_proxy(addr, r.egress_ip)
        state.blacklist_add(addr, "manual")
        assert r.in_blacklist is True
        assert r.ip_blacklist_reason == "blacklist from Test Source"

        state.blacklist_remove(addr)
        assert r.in_blacklist is False
        assert r.blacklist_reason == ""
        # Downloaded IP blacklist status must be preserved/reevaluated.
        assert r.ip_blacklist_reason == "blacklist from Test Source"
        assert r.ip_blacklist_hits == 1

    def test_blacklist_file_loads_sets_in_blacklist(self, state, tmp_data_dir):
        addr = "1.2.3.4:8080"
        r = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1, checks_ok=1)
        state.ratings[addr] = r
        # Insert directly into the DB blacklist table
        conn = state._db()
        conn.execute("INSERT INTO blacklist (address, reason) VALUES (?, ?)", (addr, "test reason"))
        conn.commit()
        conn.close()
        state._load_blacklist_file()
        assert state.blacklist[addr] == "test reason"
        assert r.in_blacklist is True
        assert r.blacklist_reason == "test reason"

    def test_ip_blacklisted_not_excluded_from_alive(self, state):
        addr = "1.2.3.4:8080"
        r = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1, checks_ok=1)
        r.egress_ip = "8.8.8.8"
        state.ratings[addr] = r
        state._parse_ip_blacklist("8.8.8.8\n", "test", "Test Source")
        state._apply_ip_blacklist_to_proxy(addr, r.egress_ip)
        assert r.is_blacklisted is True
        assert r.in_blacklist is False

        alive = [x for x in state.ratings.values() if x.last_status == "ok" and not x.in_blacklist]
        assert addr in {x.address for x in alive}
        snapshot = state.get_snapshot()
        assert addr in {x["address"] for x in snapshot["top_proxies"]}
        assert snapshot["counts"]["ip_blacklisted"] == 1
        assert snapshot["counts"]["blacklist"] == 1  # manual (0) + ip_blacklisted (1)
