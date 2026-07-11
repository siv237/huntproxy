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

    @pytest.mark.asyncio
    async def test_hunt_skip_rejected_when_idle(self, http_client, api_server):
        _, state = api_server
        resp = await http_client("POST", "/api/hunt/skip")
        status, data = json_body(resp)
        assert status == 200
        assert data.get("ok") is False


class TestApiLogs:
    @pytest.mark.asyncio
    async def test_logs_returns_events(self, http_client, api_server):
        _, state = api_server
        # Emit some events so the events table has data
        state._emit("test info message", "info")
        state._emit("test warn message", "warn")
        state._emit("test error message", "error")
        resp = await http_client("GET", "/api/logs?limit=10")
        status, data = json_body(resp)
        assert status == 200
        assert "events" in data
        assert isinstance(data["events"], list)
        assert len(data["events"]) > 0
        ev = data["events"][0]
        assert "ts" in ev
        assert "seq" in ev
        assert "type" in ev
        assert "msg" in ev

    @pytest.mark.asyncio
    async def test_logs_type_filter(self, http_client, api_server):
        _, state = api_server
        state._emit("info event", "info")
        state._emit("warn event", "warn")
        state._emit("error event", "error")
        resp = await http_client("GET", "/api/logs?limit=50&type=warn")
        status, data = json_body(resp)
        assert status == 200
        assert "events" in data
        types = {ev["type"] for ev in data["events"]}
        assert types == {"warn"}

    @pytest.mark.asyncio
    async def test_logs_limit(self, http_client, api_server):
        _, state = api_server
        for i in range(10):
            state._emit(f"bulk event {i}", "info")
        resp = await http_client("GET", "/api/logs?limit=3")
        status, data = json_body(resp)
        assert status == 200
        assert len(data["events"]) <= 3


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

    @pytest.mark.asyncio
    async def test_transparent_status(self, http_client):
        resp = await http_client("GET", "/api/transparent/status")
        status, data = json_body(resp)
        assert status == 200
        assert "running" in data
        assert "port" in data

    @pytest.mark.asyncio
    async def test_interception(self, http_client):
        resp = await http_client("GET", "/api/interception")
        status, data = json_body(resp)
        assert status == 200
        assert "own_ips" in data
        assert isinstance(data["own_ips"], list)
        assert "proxy_pid" in data
        assert "proxy_uid" in data
        assert "apply_command" in data and "revert_command" in data
        assert "--exclude-cgroup" in data["apply_command"]
        assert "--cgroup-pid" in data["apply_command"]
        assert data["revert_command"] == "sudo ./setup_iptables.sh stop"
        assert "status" in data and isinstance(data["status"], dict)
        assert "readiness" in data and isinstance(data["readiness"], dict)
        assert "ready" in data["readiness"]
        assert "blockers" in data["readiness"]

    @pytest.mark.asyncio
    async def test_interception_apply_requires_readiness(self, http_client):
        # Tests run as a non-root user, so can_apply is False and the
        # one-click apply must be rejected (never touches iptables).
        resp = await http_client("POST", "/api/interception/apply")
        status, data = json_body(resp)
        assert status == 409
        assert data["ok"] is False
        assert "readiness" in data

    @pytest.mark.asyncio
    async def test_interception_stop_resolves(self, http_client):
        # Stop must resolve (no 404) even if it fails to run iptables as
        # non-root — the endpoint itself must never vanish.
        resp = await http_client("POST", "/api/interception/stop")
        status, _ = json_body(resp)
        assert status != 404


class TestApiSettings:
    @pytest.mark.asyncio
    async def test_settings_get(self, http_client):
        resp = await http_client("GET", "/api/settings")
        status, data = json_body(resp)
        assert status == 200
        assert "proxies" in data

    @pytest.mark.asyncio
    async def test_settings_country_filter_post(self, http_client, api_server):
        _, state = api_server
        resp = await http_client("POST", "/api/settings/country_filter?code=US")
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


class TestApiSchedules:
    @pytest.mark.asyncio
    async def test_schedules_list_empty(self, http_client, api_server):
        _, state = api_server
        resp = await http_client("GET", "/api/schedules")
        status, data = json_body(resp)
        assert status == 200
        assert "schedules" in data
        assert isinstance(data["schedules"], list)

    @pytest.mark.asyncio
    async def test_schedules_list_with_scheduler(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            resp = await http_client("GET", "/api/schedules")
            status, data = json_body(resp)
            assert status == 200
            assert len(data["schedules"]) > 0
            assert "status" in data
        finally:
            await sched.stop()

    @pytest.mark.asyncio
    async def test_schedule_create(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            body = json.dumps({
                "id": "test_api_sched",
                "name": "Test API Schedule",
                "task_type": "clear_dead",
                "interval_sec": 600,
            })
            resp = await http_client("POST", "/api/schedules", body)
            status, data = json_body(resp)
            assert status == 200
            assert data["ok"] is True
            assert data["schedule"]["id"] == "test_api_sched"
        finally:
            await sched.stop()

    @pytest.mark.asyncio
    async def test_schedule_update(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            body = json.dumps({"interval_sec": 300})
            resp = await http_client("POST", "/api/schedules/history", body)
            status, data = json_body(resp)
            assert status == 200
            assert data["ok"] is True
            assert data["schedule"]["interval_sec"] == 300
        finally:
            await sched.stop()

    @pytest.mark.asyncio
    async def test_schedule_delete(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            resp = await http_client("DELETE", "/api/schedules/history")
            status, data = json_body(resp)
            assert status == 200
            assert data["ok"] is True
        finally:
            await sched.stop()

    @pytest.mark.asyncio
    async def test_schedule_toggle(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            resp = await http_client("POST", "/api/schedules/history/toggle")
            status, data = json_body(resp)
            assert status == 200
            assert data["ok"] is True
            assert "enabled" in data
        finally:
            await sched.stop()

    @pytest.mark.asyncio
    async def test_schedule_run_now(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            resp = await http_client("POST", "/api/schedules/history/run")
            status, data = json_body(resp)
            assert status == 200
            assert data["ok"] is True
        finally:
            await sched.stop()

    @pytest.mark.asyncio
    async def test_schedules_status(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            resp = await http_client("GET", "/api/schedules/status")
            status, data = json_body(resp)
            assert status == 200
            assert "running" in data
            assert "paused" in data
        finally:
            await sched.stop()

    @pytest.mark.asyncio
    async def test_schedules_pause_resume(self, http_client, api_server):
        _, state = api_server
        from hunt.scheduler import SchedulerEngine
        sched = SchedulerEngine(state)
        await sched._load_schedules()
        await sched._seed_defaults_if_empty()
        state.scheduler = sched
        try:
            resp = await http_client("POST", "/api/schedules/pause")
            status, data = json_body(resp)
            assert status == 200
            assert data["ok"] is True
            assert data["paused"] is True

            resp = await http_client("POST", "/api/schedules/resume")
            status, data = json_body(resp)
            assert status == 200
            assert data["ok"] is True
            assert data["paused"] is False
        finally:
            await sched.stop()
