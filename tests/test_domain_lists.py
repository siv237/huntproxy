import hunt


class TestDomainLists:
    def test_create_and_get_domain_list(self, state):
        data = {
            "id": "test-list",
            "name": "Test List",
            "source": "manual",
            "route": "direct",
            "enabled": True,
            "domains": ["example.com", "test.org"],
        }
        created = state.create_domain_list(data)
        assert created is not None
        assert created["id"] == "test-list"
        assert created["name"] == "Test List"
        assert created["route"] == "direct"
        assert created["enabled"] == 1
        assert set(created["domains"]) == {"example.com", "test.org"}

    def test_create_domain_list_missing_fields(self, state):
        assert state.create_domain_list({"id": "x"}) is None
        assert state.create_domain_list({"name": "x"}) is None

    def test_update_domain_list(self, state):
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "source": "manual",
            "domains": ["example.com"],
        })
        updated = state.update_domain_list("test-list", {
            "name": "Renamed List",
            "domains": ["example.com", "new.org"],
        })
        assert updated is not None
        assert updated["name"] == "Renamed List"
        assert set(updated["domains"]) == {"example.com", "new.org"}

    def test_update_domain_list_preserves_source(self, state):
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "source": "blocklist",
            "route": "pool",
            "domains": ["example.com"],
        })
        updated = state.update_domain_list("test-list", {
            "name": "Renamed List",
            "route": "direct",
        })
        assert updated is not None
        assert updated["source"] == "blocklist"
        assert updated["route"] == "direct"

    def test_delete_domain_list(self, state):
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "domains": ["example.com"],
        })
        assert state.delete_domain_list("test-list") is True
        assert state.get_domain_list("test-list") is None

    def test_toggle_domain_list(self, state):
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "enabled": True,
        })
        original = state.get_domain_list("test-list")["enabled"]
        toggled = state.toggle_domain_list("test-list")
        assert toggled["enabled"] != original

    def test_list_domain_lists(self, state):
        state.create_domain_list({"id": "list-1", "name": "List 1"})
        state.create_domain_list({"id": "list-2", "name": "List 2"})
        lists = state.get_domain_lists()
        assert len(lists) == 2
        ids = {l["id"] for l in lists}
        assert ids == {"list-1", "list-2"}


class TestRouting:
    def test_routing_disabled_by_default(self, state):
        status = state.get_routing_status()
        assert status.get("enabled") is False

    def test_routing_enable_disable(self, state):
        state.routing_enable()
        assert state.get_routing_status().get("enabled") is True
        state.routing_disable()
        assert state.get_routing_status().get("enabled") is False

    def test_routing_default_route(self, state):
        state.routing_set_default("direct")
        status = state.get_routing_status()
        assert status.get("default_route") == "direct"

    def test_routing_test_disabled(self, state):
        result = state.routing_test("example.com")
        assert result["domain"] == "example.com"
        assert result["routing_enabled"] is False

    def test_routing_test_match(self, state):
        state.routing_enable()
        state.routing_set_default("pool")
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "route": "direct",
            "enabled": True,
            "domains": ["example.com"],
        })
        result = state.routing_test("example.com")
        assert result["routing_enabled"] is True
        assert result["route"] == "direct"
        assert result["matched_list"] == "Test List"

    def test_routing_test_no_match(self, state):
        state.routing_enable()
        state.routing_set_default("pool")
        result = state.routing_test("unknown.com")
        assert result["route"] == "pool"
        assert result["matched_list"] is None

    def test_routing_test_subdomain_matches_bare(self, state):
        state.routing_enable()
        state.routing_set_default("pool")
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "route": "direct",
            "enabled": True,
            "domains": ["youtube.com"],
        })
        result = state.routing_test("www.youtube.com")
        assert result["routing_enabled"] is True
        assert result["route"] == "direct"
        assert result["matched_list"] == "Test List"

    def test_routing_test_wildcard_subdomain(self, state):
        state.routing_enable()
        state.routing_set_default("pool")
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "route": "direct",
            "enabled": True,
            "domains": ["*.youtube.com"],
        })
        assert state.routing_test("www.youtube.com")["route"] == "direct"
        assert state.routing_test("m.youtube.com")["route"] == "direct"
        assert state.routing_test("youtube.com")["route"] == "direct"
        assert state.routing_test("notyoutube.com")["route"] == "pool"

    def test_routing_test_dot_prefix(self, state):
        state.routing_enable()
        state.routing_set_default("pool")
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "route": "direct",
            "enabled": True,
            "domains": [".youtube.com"],
        })
        assert state.routing_test("www.youtube.com")["route"] == "direct"
        assert state.routing_test("youtube.com")["route"] == "direct"
        assert state.routing_test("notyoutube.com")["route"] == "pool"

    def test_resolve_route_subdomain(self, state):
        state.routing_enable()
        state.routing_set_default("pool")
        state.create_domain_list({
            "id": "test-list",
            "name": "Test List",
            "route": "direct",
            "enabled": True,
            "domains": ["youtube.com"],
        })
        assert state._resolve_route("www.youtube.com") == "direct"
        assert state._resolve_route("youtube.com") == "direct"

    def test_domain_matches_suffix(self, state):
        assert state._domain_matches("www.example.com", ["example.com"]) is True
        assert state._domain_matches("www.example.com", [".example.com"]) is True
        assert state._domain_matches("other.com", ["example.com"]) is False
