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


class TestProxySourceEntries:
    def test_replace_proxy_source_entries(self, state):
        text = "1.2.3.4:8080\n5.6.7.8:3128\n"
        found = state._parse_source_text(text)
        state._replace_proxy_source_entries("src1", found)
        conn = state._db()
        rows = conn.execute("SELECT address FROM proxy_source_entries WHERE source_id='src1'").fetchall()
        conn.close()
        assert {r["address"] for r in rows} == {"1.2.3.4:8080", "5.6.7.8:3128"}

    def test_replace_only_affects_one_source(self, state):
        state._replace_proxy_source_entries("src1", {"1.2.3.4:8080"})
        state._replace_proxy_source_entries("src2", {"1.2.3.4:8080", "5.6.7.8:3128"})
        state._replace_proxy_source_entries("src1", {"5.6.7.8:3128"})
        conn = state._db()
        rows = conn.execute("SELECT source_id, address FROM proxy_source_entries").fetchall()
        conn.close()
        pairs = {(r["source_id"], r["address"]) for r in rows}
        assert ("src1", "5.6.7.8:3128") in pairs
        assert ("src2", "1.2.3.4:8080") in pairs
        assert ("src2", "5.6.7.8:3128") in pairs
        assert ("src1", "1.2.3.4:8080") not in pairs

    def test_load_all_proxy_source_entries(self, state):
        state._replace_proxy_source_entries("src1", {"1.2.3.4:8080"})
        state._load_all_proxy_source_entries()
        assert state._source_proxies.get("src1") == {"1.2.3.4:8080"}
        assert state._addr_sources.get("1.2.3.4:8080") == ["src1"]

    def test_delete_proxy_source_removes_entries(self, state):
        data = {"id": "src-del", "name": "Delete Source", "url": "https://example.com/proxies.txt", "enabled": True}
        created = state.create_proxy_source(data)
        assert created is not None
        state._replace_proxy_source_entries("src-del", {"1.2.3.4:8080"})
        state._load_all_proxy_source_entries()
        assert state._source_proxies.get("src-del") == {"1.2.3.4:8080"}
        state.delete_proxy_source("src-del")
        conn = state._db()
        count = conn.execute("SELECT COUNT(*) as c FROM proxy_source_entries WHERE source_id='src-del'").fetchone()["c"]
        conn.close()
        assert count == 0
        assert state._source_proxies.get("src-del") is None

    def test_toggle_disable_clears_proxy_source_entries(self, state):
        data = {"id": "src-toggle", "name": "Toggle Source", "url": "https://example.com/proxies.txt", "enabled": True}
        created = state.create_proxy_source(data)
        assert created is not None
        state._replace_proxy_source_entries("src-toggle", {"1.2.3.4:8080"})
        state._load_all_proxy_source_entries()
        assert "1.2.3.4:8080" in state._source_proxies.get("src-toggle", set())
        state.toggle_proxy_source("src-toggle")
        assert state._source_proxies.get("src-toggle") is None
        conn = state._db()
        count = conn.execute("SELECT COUNT(*) as c FROM proxy_source_entries WHERE source_id='src-toggle'").fetchone()["c"]
        conn.close()
        assert count == 0

    def test_update_disable_clears_proxy_source_entries(self, state):
        data = {"id": "src-update", "name": "Update Source", "url": "https://example.com/proxies.txt", "enabled": True}
        created = state.create_proxy_source(data)
        assert created is not None
        state._replace_proxy_source_entries("src-update", {"1.2.3.4:8080"})
        state._load_all_proxy_source_entries()
        assert "1.2.3.4:8080" in state._source_proxies.get("src-update", set())
        state.update_proxy_source("src-update", {"enabled": False})
        assert state._source_proxies.get("src-update") is None
        conn = state._db()
        count = conn.execute("SELECT COUNT(*) as c FROM proxy_source_entries WHERE source_id='src-update'").fetchone()["c"]
        conn.close()
        assert count == 0

    def test_current_entries_in_api(self, state):
        data = {"id": "src-cur", "name": "Current Source", "url": "https://example.com/proxies.txt", "enabled": True}
        created = state.create_proxy_source(data)
        assert created is not None
        state._replace_proxy_source_entries("src-cur", {"1.2.3.4:8080", "5.6.7.8:3128"})
        source = state.get_proxy_source("src-cur")
        assert source["current_entries"] == 2
        sources = state.get_proxy_sources()
        found = next((s for s in sources if s["id"] == "src-cur"), None)
        assert found is not None
        assert found["current_entries"] == 2
