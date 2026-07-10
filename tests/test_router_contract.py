"""Router contract — every API endpoint must respond (not 404).

This is the safety net for the ``server.py`` router extraction.  When
the monolithic ``_route`` method is split into a registry of handlers,
these tests verify that no endpoint was accidentally dropped.

Tagged ``router`` so they can be run in isolation:

    ./test.sh -m router          # router contract only
    ./test.sh -m "not router"    # everything except router

GET endpoints are tested for a non-404 response.  POST/DELETE endpoints
are tested for a non-404 response (they may return 400/500 if the body
is wrong, but must never 404 — that means the route vanished).
"""

import asyncio
import json
import pytest

from tests.test_api import parse_response, json_body


# ── GET endpoints — must return 200 or a structured error (never 404) ──

GET_ENDPOINTS = [
    "/",
    "/api/snapshot",
    "/api/countries",
    "/api/favorites",
    "/api/proxy/status",
    "/api/proxy/alive",
    "/api/socks5/status",
    "/api/transparent/status",
    "/api/interception",
    "/api/settings",
    "/api/proxy-sources",
    "/api/ip-blacklists",
    "/api/ip-blacklists/progress",
    "/api/ip-blacklist/entries?limit=5",
    "/api/ip-blacklist/matches",
    "/api/blocklists",
    "/api/blocklists/progress",
    "/api/custom-proxies",
    "/api/domain-lists",
    "/api/routing/status",
    "/api/canary/status",
    "/api/schedules",
    "/api/schedules/status",
    "/api/schedules/log?limit=5",
    "/api/backup/groups",
    "/api/downloads/count",
    "/api/proxy-sources/progress",
    "/api/traffic",
    "/api/actions?limit=5",
    "/api/logs?limit=5",
    "/favicon.ico",
    "/css/layout.css",
    "/js/app.js",
]

# ── POST endpoints — must not 404 (body may be wrong → 400/500 is OK) ──

POST_ENDPOINTS = [
    "/api/hunt/start",
    "/api/hunt/stop",
    "/api/hunt/pause",
    "/api/hunt/resume",
    "/api/hunt/skip",
    "/api/blacklist/add",
    "/api/blacklist/remove",
    "/api/favorites/add",
    "/api/favorites/remove",
    "/api/proxy/stop",
    "/api/socks5/stop",
    "/api/transparent/stop",
    "/api/settings/country_filter?code=US",
    "/api/schedules/pause",
    "/api/schedules/resume",
    "/api/schedules/restore-defaults",
    "/api/canary/hosts",
    "/api/channel/select",
    "/api/clear_dead",
    "/api/blocklists/fetch",
    "/api/ip-blacklists/fetch",
    "/api/proxy-sources/fetch",
]

DELETE_ENDPOINTS = [
    "/api/schedules/history",
]


class TestRouterGetEndpoints:
    """Every GET endpoint must resolve (200 or structured error, never 404)."""

    @pytest.mark.router
    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", GET_ENDPOINTS)
    async def test_get_endpoint_resolves(self, http_client, endpoint):
        resp = await http_client("GET", endpoint)
        status, _, body = parse_response(resp)
        assert status != 404, (
            f"GET {endpoint} → 404 — route vanished during refactor"
        )

    @pytest.mark.router
    @pytest.mark.asyncio
    async def test_get_snapshot_has_required_keys(self, http_client):
        """Snapshot is the most-used endpoint — its contract is frozen."""
        resp = await http_client("GET", "/api/snapshot")
        status, data = json_body(resp)
        assert status == 200
        for key in ("phase", "running", "paused", "progress", "counts",
                     "top_proxies", "scheduler"):
            assert key in data, f"snapshot missing key '{key}'"

    @pytest.mark.router
    @pytest.mark.asyncio
    async def test_get_schedules_with_scheduler(self, http_client, api_server):
        """Schedules endpoint needs a live scheduler to return data."""
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched.prepare()
        state.scheduler = sched
        try:
            resp = await http_client("GET", "/api/schedules")
            status, data = json_body(resp)
            assert status == 200
            assert len(data["schedules"]) > 0
        finally:
            await sched.stop()


class TestRouterPostEndpoints:
    """Every POST endpoint must resolve (never 404)."""

    @pytest.mark.router
    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", POST_ENDPOINTS)
    async def test_post_endpoint_resolves(self, http_client, endpoint):
        resp = await http_client("POST", endpoint, body=b"{}")
        status, _, body = parse_response(resp)
        assert status != 404, (
            f"POST {endpoint} → 404 — route vanished during refactor"
        )

    @pytest.mark.router
    @pytest.mark.asyncio
    async def test_post_blacklist_add_works(self, http_client, api_server):
        """Blacklist add is a representative POST that mutates state."""
        _, state = api_server
        resp = await http_client("POST", "/api/blacklist/add",
                                  body=json.dumps({"address": "9.9.9.9:9999", "reason": "test"}))
        status, data = json_body(resp)
        assert status == 200
        assert data["ok"] is True
        assert "9.9.9.9:9999" in state.blacklist


class TestRouterDeleteEndpoints:
    """Every DELETE endpoint must resolve (never 404)."""

    @pytest.mark.router
    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", DELETE_ENDPOINTS)
    async def test_delete_endpoint_resolves(self, http_client, endpoint):
        _, state = api_server if "api_server" in {} else (None, None)
        resp = await http_client("DELETE", endpoint)
        status, _, body = parse_response(resp)
        assert status != 404, (
            f"DELETE {endpoint} → 404 — route vanished during refactor"
        )


class TestRouterScheduleSubpaths:
    """Schedule sub-path routes (/run, /stop, /toggle) must resolve."""

    @pytest.mark.router
    @pytest.mark.asyncio
    async def test_schedule_run_now_resolves(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched.prepare()
        state.scheduler = sched
        try:
            resp = await http_client("POST", "/api/schedules/history/run")
            status, data = json_body(resp)
            assert status != 404
        finally:
            await sched.stop()

    @pytest.mark.router
    @pytest.mark.asyncio
    async def test_schedule_toggle_resolves(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched.prepare()
        state.scheduler = sched
        try:
            resp = await http_client("POST", "/api/schedules/history/toggle")
            status, data = json_body(resp)
            assert status != 404
        finally:
            await sched.stop()

    @pytest.mark.router
    @pytest.mark.asyncio
    async def test_schedule_update_resolves(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched.prepare()
        state.scheduler = sched
        try:
            resp = await http_client("POST", "/api/schedules/history",
                                      body=json.dumps({"interval_sec": 300}))
            status, data = json_body(resp)
            assert status != 404
        finally:
            await sched.stop()
