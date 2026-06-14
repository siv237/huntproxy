import pytest
import hunt


class TestProxySourceParsing:
    def test_parse_source_text_plain(self, state):
        text = "1.2.3.4:8080\n5.6.7.8:3128\n"
        seen = state._parse_source_text(text)
        assert len(seen) == 2
        assert "1.2.3.4:8080" in seen
        assert "5.6.7.8:3128" in seen

    def test_parse_source_text_with_protocol_prefix(self, state):
        text = "http://1.2.3.4:8080\nsocks5://5.6.7.8:1080\n"
        seen = state._parse_source_text(text)
        assert "1.2.3.4:8080" in seen
        assert "5.6.7.8:1080" in seen

    def test_parse_source_text_skips_comments_and_empty(self, state):
        text = "# comment\n\n1.2.3.4:8080\ninvalid line\n"
        seen = state._parse_source_text(text)
        assert len(seen) == 1
        assert "1.2.3.4:8080" in seen

    def test_parse_source_text_invalid_addresses(self, state):
        text = "1.2.3.4\n1.2.3.4:abc\n1.2.3.4:8080\n"
        seen = state._parse_source_text(text)
        assert len(seen) == 1
        assert "1.2.3.4:8080" in seen

    def test_parse_source_text_ignores_out_of_range_ports(self, state):
        text = "1.2.3.4:0\n1.2.3.4:70000\n1.2.3.4:8080\n"
        seen = state._parse_source_text(text)
        assert len(seen) == 1
        assert "1.2.3.4:8080" in seen


class TestProxySourceDb:
    def test_proxy_source_crud_in_db(self, state):
        sources = state.get_proxy_sources()
        assert isinstance(sources, list)
        # default sources should be seeded
        assert len(sources) > 0

    def test_proxy_source_toggle(self, state):
        sources = state.get_proxy_sources()
        if not sources:
            pytest.skip("no sources to toggle")
        sid = sources[0]["id"]
        original = sources[0]["enabled"]
        state.toggle_proxy_source(sid)
        updated = state.get_proxy_sources()
        found = next((s for s in updated if s["id"] == sid), None)
        assert found is not None
        assert found["enabled"] != original
        # toggle back
        state.toggle_proxy_source(sid)
        updated2 = state.get_proxy_sources()
        found2 = next((s for s in updated2 if s["id"] == sid), None)
        assert found2["enabled"] == original

    def test_create_and_delete_proxy_source(self, state):
        data = {"id": "test-source", "name": "Test Source", "url": "https://example.com/proxies.txt", "enabled": True}
        created = state.create_proxy_source(data)
        assert created is not None
        sid = created["id"]
        assert state.get_proxy_source(sid) is not None
        assert state.delete_proxy_source(sid) is True
        assert state.get_proxy_source(sid) is None

    def test_update_proxy_source(self, state):
        sources = state.get_proxy_sources()
        if not sources:
            pytest.skip("no sources to update")
        sid = sources[0]["id"]
        updated = state.update_proxy_source(sid, {"name": "Renamed Source"})
        assert updated is not None
        assert updated["name"] == "Renamed Source"
