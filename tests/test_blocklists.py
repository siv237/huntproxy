import pytest
import asyncio
import sqlite3


class TestBlocklistSources:
    def test_seed_default_blocklists(self, state):
        sources = state.get_blocklist_sources()
        assert len(sources) >= 4
        ids = {s["id"] for s in sources}
        assert "ru-rkn-ip" in ids
        assert "ru-rkn-domains" in ids
        assert "ru-inside-domains" in ids
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
            assert s["direction"] in ("inside", "outside", "domestic")
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
        count = state._parse_domain_blocklist(text, "test-dom-bl", "Test Domain BL", route="pool")
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

    def test_parse_domain_blocklist_white_route_direct(self, state):
        text = "gosuslugi.ru\n"
        count = state._parse_domain_blocklist(text, "test-white-bl", "White BL", route="direct")
        assert count == 1
        dl = state.get_domain_list("test-white-bl")
        assert dl["route"] == "direct"

    def test_parse_domain_blocklist_strips_port(self, state):
        text = "yandex.ru:443\nalfa-bank.ru:443\n"
        count = state._parse_domain_blocklist(text, "test-port-bl", "Port BL", route="direct")
        assert count == 2
        domains = set(state.get_domain_list("test-port-bl")["domains"])
        assert domains == {"yandex.ru", "alfa-bank.ru"}

    def test_parse_domain_blocklist_clash_format(self, state):
        text = (
            "payload:\n"
            "  - 'DOMAIN-SUFFIX,vk.com'\n"
            "  - 'DOMAIN,vk.ru'\n"
            "  - 'IP-CIDR,10.0.0.0/8,no-resolve'\n"
        )
        count = state._parse_domain_blocklist(text, "test-clash-bl", "Clash BL", route="direct")
        assert count == 2
        domains = set(state.get_domain_list("test-clash-bl")["domains"])
        assert "*.vk.com" in domains
        assert "vk.ru" in domains

    def test_parse_domain_blocklist_v2fly_format(self, state):
        text = (
            "domain-suffix:vk.com\n"
            "domain:vk.ru\n"
            "full:ok.ru\n"
        )
        count = state._parse_domain_blocklist(text, "test-v2fly-bl", "V2fly BL", route="direct")
        assert count == 3
        domains = set(state.get_domain_list("test-v2fly-bl")["domains"])
        assert "*.vk.com" in domains
        assert "vk.ru" in domains
        assert "ok.ru" in domains

    def test_parse_domain_blocklist_dedup(self, state):
        text = "a.com\na.com\nb.com\na.com\n"
        count = state._parse_domain_blocklist(text, "test-dedup-bl", "Dedup BL", route="pool")
        assert count == 2

    def test_parse_domain_blocklist_empty(self, state):
        count = state._parse_domain_blocklist("# only comments\n\n", "test-empty-bl", "Empty BL", route="pool")
        assert count == 0

    def test_parse_domain_blocklist_update_replaces(self, state):
        state._parse_domain_blocklist("a.com\nb.com", "test-replace-bl", "Replace BL", route="pool")
        assert len(state.get_domain_list("test-replace-bl")["domains"]) == 2
        state._parse_domain_blocklist("c.com\nd.com", "test-replace-bl", "Replace BL", route="pool")
        domains = set(state.get_domain_list("test-replace-bl")["domains"])
        assert domains == {"c.com", "d.com"}


class _Row:
    def __init__(self, d):
        self._d = d

    def keys(self):
        return self._d.keys()

    def __getitem__(self, k):
        return self._d[k]


class TestRouteForSource:
    def test_white_defaults_direct(self, state):
        assert state._route_for_source(_Row({"class": "white", "route": ""})) == "direct"

    def test_block_defaults_pool(self, state):
        assert state._route_for_source(_Row({"class": "block", "route": ""})) == "pool"

    def test_explicit_route_wins(self, state):
        assert state._route_for_source(_Row({"class": "white", "route": "custom:x"})) == "custom:x"

    def test_missing_columns_default_pool(self, state):
        assert state._route_for_source(_Row({"id": "x"})) == "pool"


class TestBlocklistMigration:
    def test_migrate_adds_new_sources(self, state):
        conn = state._db()
        conn.execute("DELETE FROM blocklist_sources")
        conn.commit()
        conn.close()
        state._migrate_blocklists()
        sources = state.get_blocklist_sources()
        assert len(sources) >= 4

    def test_migrate_updates_changed_url(self, state):
        from hunt.constants import DEFAULT_BLOCKLIST_SOURCES
        bl = {b[0]: b for b in DEFAULT_BLOCKLIST_SOURCES}
        sid = "ru-geoblock-domains"
        new_url = bl[sid][5]
        conn = state._db()
        conn.execute(
            "UPDATE blocklist_sources SET url='https://old.example/stale.lst' WHERE id=?",
            (sid,)
        )
        conn.commit()
        conn.close()
        state._migrate_blocklists()
        src = state.get_blocklist_source(sid)
        assert src["url"] == new_url

    def test_migrate_removes_stale_sources(self, state):
        from hunt.constants import DEFAULT_BLOCKLIST_SOURCES
        current_sids = {s[0] for s in DEFAULT_BLOCKLIST_SOURCES}
        conn = state._db()
        conn.execute(
            "INSERT INTO blocklist_sources "
            "(id, name, country, direction, list_type, url, enabled, priority, created_at, updated_at) "
            "VALUES ('ru-banned-domains','Stale','RU','outside','domain','https://stale.example/x',1,99,0,0)"
        )
        conn.execute(
            "INSERT INTO domain_lists (id, name, source, url, route, enabled, priority, created_at, updated_at) "
            "VALUES ('ru-banned-domains','Stale','blocklist','','pool',1,99,0,0)"
        )
        conn.execute("INSERT INTO domain_entries (list_id, pattern) VALUES ('ru-banned-domains','dzen.ru')")
        conn.commit()
        conn.close()
        assert "ru-banned-domains" not in current_sids
        state._migrate_blocklists()
        assert state.get_blocklist_source("ru-banned-domains") is None
        conn = state._db()
        dl = conn.execute("SELECT id FROM domain_lists WHERE id='ru-banned-domains'").fetchone()
        de = conn.execute("SELECT list_id FROM domain_entries WHERE list_id='ru-banned-domains'").fetchone()
        conn.close()
        assert dl is None
        assert de is None
