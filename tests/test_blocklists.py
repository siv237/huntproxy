import pytest
import asyncio
import sqlite3


class TestBlocklistSources:
    def test_seed_default_blocklists(self, state):
        sources = state.get_blocklist_sources()
        assert len(sources) >= 3
        ids = {s["id"] for s in sources}
        assert "ru-rkn-ip" in ids
        assert "ru-rkn-domains" in ids
        assert "ru-geoblock-domains" in ids

    def test_seed_idempotent(self, state):
        state._seed_default_blocklists()
        state._seed_default_blocklists()
        sources = state.get_blocklist_sources()
        ids = [s["id"] for s in sources]
        assert len(ids) == len(set(ids))

    def test_default_sources_have_country_and_direction(self, state):
        sources = {s["id"]: s for s in state.get_blocklist_sources()}
        for s in sources.values():
            assert s["country"] != ""
            assert s["direction"] in ("inside", "outside")
            assert s["list_type"] in ("ip", "domain")
        assert sources["ru-rkn-ip"]["country"] == "RU"
        assert sources["ru-rkn-ip"]["direction"] == "inside"
        assert sources["ru-rkn-ip"]["list_type"] == "ip"
        assert sources["ru-geoblock-domains"]["direction"] == "outside"
        assert sources["ru-geoblock-domains"]["list_type"] == "domain"

    def test_create_blocklist_source(self, state):
        result = state.create_blocklist_source({
            "id": "test-bl",
            "name": "Test Blocklist",
            "country": "US",
            "direction": "inside",
            "list_type": "ip",
            "url": "https://example.com/list.txt",
            "download_proxy": "socks5://127.0.0.1:17278",
        })
        assert result is not None
        assert result["id"] == "test-bl"
        assert result["country"] == "US"
        assert result["direction"] == "inside"
        assert result["download_proxy"] == "socks5://127.0.0.1:17278"

    def test_create_blocklist_source_missing_fields(self, state):
        assert state.create_blocklist_source({"id": "x"}) is None
        assert state.create_blocklist_source({"id": "x", "name": "X"}) is None

    def test_toggle_blocklist_source(self, state):
        result = state.toggle_blocklist_source("ru-rkn-ip")
        assert result is not None
        assert result["enabled"] == 0
        result = state.toggle_blocklist_source("ru-rkn-ip")
        assert result["enabled"] == 1

    def test_delete_blocklist_source(self, state):
        state.create_blocklist_source({
            "id": "del-bl",
            "name": "Delete Me",
            "country": "XX",
            "direction": "inside",
            "list_type": "ip",
            "url": "https://example.com/del.txt",
        })
        assert state.delete_blocklist_source("del-bl") is True
        assert state.get_blocklist_source("del-bl") is None

    def test_delete_nonexistent(self, state):
        assert state.delete_blocklist_source("nonexistent") is False

    def test_update_blocklist_source(self, state):
        state.create_blocklist_source({
            "id": "upd-bl",
            "name": "Old Name",
            "country": "XX",
            "direction": "inside",
            "list_type": "ip",
            "url": "https://example.com/old.txt",
            "download_proxy": "",
        })
        result = state.update_blocklist_source("upd-bl", {
            "name": "New Name",
            "country": "YY",
            "direction": "outside",
            "list_type": "domain",
            "url": "https://example.com/new.txt",
            "download_proxy": "socks5://127.0.0.1:17278",
        })
        assert result is not None
        assert result["name"] == "New Name"
        assert result["country"] == "YY"
        assert result["direction"] == "outside"
        assert result["list_type"] == "domain"
        assert result["download_proxy"] == "socks5://127.0.0.1:17278"


class TestBlocklistParse:
    def test_parse_domain_blocklist_creates_domain_list(self, state):
        text = "example.com\nblocked.org\n# comment\n\n.bad-suffix.com\n"
        count = state._parse_domain_blocklist(text, "test-dom-bl", "Test Domain BL")
        assert count == 3
        dl = state.get_domain_list("test-dom-bl")
        assert dl is not None
        assert dl["source"] == "blocklist"
        assert dl["route"] == "pool"
        assert dl["enabled"] == 1
        domains = set(dl["domains"])
        assert "example.com" in domains
        assert "blocked.org" in domains
        assert ".bad-suffix.com" in domains

    def test_parse_domain_blocklist_dedup(self, state):
        text = "a.com\na.com\nb.com\na.com\n"
        count = state._parse_domain_blocklist(text, "test-dedup-bl", "Dedup BL")
        assert count == 2

    def test_parse_domain_blocklist_empty(self, state):
        count = state._parse_domain_blocklist("# only comments\n\n", "test-empty-bl", "Empty BL")
        assert count == 0

    def test_parse_domain_blocklist_update_replaces(self, state):
        state._parse_domain_blocklist("a.com\nb.com", "test-replace-bl", "Replace BL")
        assert len(state.get_domain_list("test-replace-bl")["domains"]) == 2
        state._parse_domain_blocklist("c.com\nd.com", "test-replace-bl", "Replace BL")
        domains = set(state.get_domain_list("test-replace-bl")["domains"])
        assert domains == {"c.com", "d.com"}


class TestBlocklistMigration:
    def test_migrate_adds_new_sources(self, state):
        conn = state._db()
        conn.execute("DELETE FROM blocklist_sources")
        conn.commit()
        conn.close()
        state._migrate_blocklists()
        sources = state.get_blocklist_sources()
        assert len(sources) >= 3
