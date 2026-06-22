import json

import hunt
import pytest

from tests.test_api import json_body


class TestFavorites:
    def test_favorite_add_and_remove(self, state):
        addr = "1.2.3.4:8080"
        state.ratings[addr] = hunt.ProxyRating(address=addr)
        state.favorite_add(addr)
        assert addr in state.favorites
        assert state.ratings[addr].is_favorite is True

        state.favorite_remove(addr)
        assert addr not in state.favorites
        assert state.ratings[addr].is_favorite is False

    def test_favorite_add_unknown_address(self, state):
        state.favorite_add("9.9.9.9:9999")
        assert "9.9.9.9:9999" in state.favorites

    def test_favorite_remove_unknown(self, state):
        state.favorite_remove("9.9.9.9:9999")

    def test_favorite_persisted_to_dict(self, state):
        addr = "1.2.3.4:8080"
        r = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1, checks_ok=1)
        state.ratings[addr] = r
        state.favorite_add(addr)
        d = r.to_dict()
        assert d["is_favorite"] is True

    @pytest.mark.asyncio
    async def test_favorite_protected_from_clear_dead(self, http_client, api_server):
        _, state = api_server
        addr = "1.2.3.4:8080"
        r = hunt.ProxyRating(address=addr, last_status="failed", checks_total=1, checks_ok=0)
        state.ratings[addr] = r
        state.favorite_add(addr)
        assert addr in state.ratings

        resp = await http_client("POST", "/api/clear_dead")
        status, data = json_body(resp)
        assert status == 200
        assert data["ok"] is True
        assert addr in state.ratings

    @pytest.mark.asyncio
    async def test_clear_dead_removes_non_favorite(self, http_client, api_server):
        _, state = api_server
        addr = "5.6.7.8:3128"
        r = hunt.ProxyRating(address=addr, last_status="failed", checks_total=1, checks_ok=0)
        state.ratings[addr] = r

        await http_client("POST", "/api/clear_dead")
        assert addr not in state.ratings

    @pytest.mark.asyncio
    async def test_clear_dead_protects_proven_proxy_in_grace(self, http_client, api_server):
        _, state = api_server
        addr = "5.6.7.8:3128"
        r = hunt.ProxyRating(
            address=addr, last_status="failed", checks_total=5, checks_ok=4,
            consecutive_fails=1, speed_sum=100, speed_count=1,
        )
        state.ratings[addr] = r

        await http_client("POST", "/api/clear_dead")
        assert addr in state.ratings

    @pytest.mark.asyncio
    async def test_clear_dead_removes_proxy_after_grace_expires(self, http_client, api_server):
        _, state = api_server
        addr = "5.6.7.8:3128"
        r = hunt.ProxyRating(
            address=addr, last_status="failed", checks_total=5, checks_ok=4,
            consecutive_fails=hunt.ProxyRating.GRACE_FAILS,
            speed_sum=100, speed_count=1,
        )
        state.ratings[addr] = r

        await http_client("POST", "/api/clear_dead")
        assert addr not in state.ratings

    @pytest.mark.asyncio
    async def test_favorite_endpoints(self, http_client, api_server):
        _, state = api_server
        addr = "1.2.3.4:8080"
        state.ratings[addr] = hunt.ProxyRating(address=addr)

        resp = await http_client("POST", "/api/favorites/add", {"address": addr})
        status, data = json_body(resp)
        assert status == 200
        assert data["ok"] is True
        assert addr in state.favorites
        assert state.ratings[addr].is_favorite is True

        resp = await http_client("POST", "/api/favorites/remove", {"address": addr})
        status, data = json_body(resp)
        assert status == 200
        assert data["ok"] is True
        assert addr not in state.favorites
        assert state.ratings[addr].is_favorite is False

    @pytest.mark.asyncio
    async def test_favorites_list_endpoint(self, http_client, api_server):
        _, state = api_server
        state.ratings["1.1.1.1:80"] = hunt.ProxyRating(address="1.1.1.1:80", last_status="ok", checks_total=1, checks_ok=1)
        state.ratings["2.2.2.2:80"] = hunt.ProxyRating(address="2.2.2.2:80", last_status="ok", checks_total=1, checks_ok=1)
        state.favorite_add("1.1.1.1:80")
        state.favorite_add("2.2.2.2:80")

        resp = await http_client("GET", "/api/favorites")
        status, data = json_body(resp)
        assert status == 200
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(d["is_favorite"] is True for d in data)

    def test_favorite_loaded_from_db(self, state):
        addr = "1.2.3.4:8080"
        state.ratings[addr] = hunt.ProxyRating(address=addr)
        state.favorite_add(addr)

        new_state = hunt.HuntState(state.config)
        assert addr in new_state.favorites
        assert new_state.ratings[addr].is_favorite is True

    def test_favorite_in_backup_groups(self, state):
        groups = state.get_backup_groups()
        keys = [g["key"] for g in groups]
        assert "favorites" in keys

    @pytest.mark.asyncio
    async def test_import_with_favorite_marks_proxies(self, http_client, api_server):
        _, state = api_server
        lines = ["1.2.3.4:8080  United States  0.500", "5.6.7.8:3128  Germany  0.300"]
        resp = await http_client("POST", "/api/import", {"proxies": lines, "favorite": True})
        status, data = json_body(resp)
        assert status == 200
        assert data["ok"] is True
        assert data["added"] == 2
        assert data["favorited"] == 2
        assert "1.2.3.4:8080" in state.favorites
        assert "5.6.7.8:3128" in state.favorites

    @pytest.mark.asyncio
    async def test_import_without_favorite_does_not_mark(self, http_client, api_server):
        _, state = api_server
        resp = await http_client("POST", "/api/import", {"proxies": ["9.9.9.9:8080"]})
        status, data = json_body(resp)
        assert status == 200
        assert data["added"] == 1
        assert "favorited" not in data
        assert "9.9.9.9:8080" not in state.favorites

    @pytest.mark.asyncio
    async def test_import_skips_comments_and_parses_first_token(self, http_client, api_server):
        _, state = api_server
        lines = [
            "# huntproxy alive working proxies (generated from DB)",
            "1.1.1.1:80  US  0.123",
            "",
            "2.2.2.2:443  DE  0.456",
        ]
        resp = await http_client("POST", "/api/import", {"proxies": lines, "favorite": True})
        status, data = json_body(resp)
        assert status == 200
        assert data["added"] == 2
        assert "1.1.1.1:80" in state.ratings
        assert "2.2.2.2:443" in state.ratings

    @pytest.mark.asyncio
    async def test_import_does_not_overwrite_existing(self, http_client, api_server):
        _, state = api_server
        addr = "3.3.3.3:8080"
        state.ratings[addr] = hunt.ProxyRating(
            address=addr, checks_total=10, checks_ok=8, last_status="ok",
            speed_sum=500, speed_count=1)
        resp = await http_client("POST", "/api/import", {"proxies": [addr], "favorite": True})
        status, data = json_body(resp)
        assert status == 200
        assert data["added"] == 0
        assert data["favorited"] == 1
        assert state.ratings[addr].checks_total == 10
        assert addr in state.favorites
