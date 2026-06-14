import asyncio
import json
import pytest


def parse_response(response: bytes):
    """Parse HTTP/1.1 response into (status, headers, body)."""
    sep = response.find(b"\r\n\r\n")
    if sep == -1:
        sep = response.find(b"\n\n")
    head = response[:sep].decode(errors="replace")
    body = response[sep + 4:] if sep != -1 else b""
    lines = head.split("\r\n")
    status_line = lines[0]
    parts = status_line.split(" ", 2)
    status = int(parts[1]) if len(parts) >= 2 else 0
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status, headers, body


def json_body(response: bytes):
    status, _, body = parse_response(response)
    return status, json.loads(body.decode(errors="replace"))


class TestApiSnapshot:
    @pytest.mark.asyncio
    async def test_snapshot_basic(self, http_client):
        resp = await http_client("GET", "/api/snapshot")
        status, data = json_body(resp)
        assert status == 200
        assert "phase" in data
        assert "top_proxies" in data
        assert "counts" in data

    @pytest.mark.asyncio
    async def test_countries(self, http_client):
        resp = await http_client("GET", "/api/countries")
        status, data = json_body(resp)
        assert status == 200
        assert isinstance(data, list)


class TestApiHunt:
    @pytest.mark.asyncio
    async def test_hunt_start_and_stop(self, http_client, api_server):
        _, state = api_server
        # start
        resp = await http_client("POST", "/api/hunt/start")
        status, data = json_body(resp)
        assert status == 200
        assert data.get("ok") is True
        # stop
        resp = await http_client("POST", "/api/hunt/stop")
        status, data = json_body(resp)
        assert status == 200
        assert data.get("ok") is True


class TestApiBlacklist:
    @pytest.mark.asyncio
    async def test_blacklist_add_and_remove(self, http_client, api_server):
        _, state = api_server
        addr = "1.2.3.4:8080"
        resp = await http_client("POST", "/api/blacklist/add", body={"address": addr, "reason": "test"})
        status, data = json_body(resp)
        assert status == 200
        assert data.get("ok") is True
        assert addr in state.blacklist

        resp = await http_client("POST", "/api/blacklist/remove", body={"address": addr})
        status, data = json_body(resp)
        assert status == 200
        assert data.get("ok") is True
        assert addr not in state.blacklist


class TestApiProxy:
    @pytest.mark.asyncio
    async def test_proxy_status(self, http_client):
        resp = await http_client("GET", "/api/proxy/status")
        status, data = json_body(resp)
        assert status == 200
        assert "running" in data

    @pytest.mark.asyncio
    async def test_proxy_alive(self, http_client):
        resp = await http_client("GET", "/api/proxy/alive")
        status, data = json_body(resp)
        assert status == 200
        assert isinstance(data, list)


class TestApiSettings:
    @pytest.mark.asyncio
    async def test_settings_get(self, http_client):
        resp = await http_client("GET", "/api/settings")
        status, data = json_body(resp)
        assert status == 200
        assert "country_filter" in data

    @pytest.mark.asyncio
    async def test_settings_country_filter_post(self, http_client, api_server):
        _, state = api_server
        resp = await http_client("POST", "/api/settings/country_filter?value=US")
        status, data = json_body(resp)
        assert status == 200
        assert data.get("ok") is True
        assert state.country_filter == "US"


class TestApiProxySources:
    @pytest.mark.asyncio
    async def test_proxy_sources_list(self, http_client):
        resp = await http_client("GET", "/api/proxy-sources")
        status, data = json_body(resp)
        assert status == 200
        assert "sources" in data


class TestApiIpBlacklists:
    @pytest.mark.asyncio
    async def test_ip_blacklists_list(self, http_client):
        resp = await http_client("GET", "/api/ip-blacklists")
        status, data = json_body(resp)
        assert status == 200
        assert "sources" in data

    @pytest.mark.asyncio
    async def test_ip_blacklist_entries(self, http_client):
        resp = await http_client("GET", "/api/ip-blacklist/entries?limit=5")
        status, data = json_body(resp)
        assert status == 200
        assert "entries" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_ip_blacklist_matches(self, http_client):
        resp = await http_client("GET", "/api/ip-blacklist/matches")
        status, data = json_body(resp)
        assert status == 200
        assert "matches" in data
        assert "total" in data


class TestApiStatic:
    @pytest.mark.asyncio
    async def test_index_html(self, http_client):
        resp = await http_client("GET", "/")
        status, headers, body = parse_response(resp)
        assert status == 200
        assert b"<html" in body.lower() or b"<!doctype" in body.lower()

    @pytest.mark.asyncio
    async def test_static_js(self, http_client):
        resp = await http_client("GET", "/js/app.js")
        status, headers, body = parse_response(resp)
        assert status in (200, 404)
        if status == 200:
            assert headers.get("content-type", "").startswith("application/javascript")
