"""Proxy ping module — source resolution and status API shape."""

import asyncio
import json

from hunt.scheduler import SchedulerEngine
from hunt.task_executor import TaskExecutor


class TestProxyPingStatus:
    async def _status(self, state):
        return state.get_proxy_ping_status()

    def test_status_shape_without_proxy(self, state):
        async def run():
            status = await self._status(state)
            assert status["source"] in ("channel", "pool", "direct")
            assert status["window"] == 60
            assert status["interval"] == 1.0
            assert isinstance(status["samples"], list)
            assert isinstance(status["last"], dict)
            assert "latency" in status["last"]
            assert isinstance(status["geo"], dict)

        asyncio.run(run())

    def test_status_endpoint_via_router(self, api_server):
        import urllib.request

        base_url, _ = api_server
        with urllib.request.urlopen(f"{base_url}/api/proxy/ping", timeout=10) as resp:
            assert resp.status == 200
            data = json.loads(resp.read())
            assert "samples" in data
            assert "source" in data

    def test_ping_source_pool_proxy(self, state):
        async def run():
            state._proxy_active_addr = "1.2.3.4:8080"
            state.ratings["1.2.3.4:8080"] = state._create_rating("1.2.3.4:8080", "RU", "ru")
            src = state._ping_source()
            assert src["kind"] == "pool"
            assert src["addr"] == "1.2.3.4:8080"
            assert src["host"] == "1.2.3.4"
            assert src["port"] == 8080

        asyncio.run(run())

    def test_ping_source_direct_fallback(self, state):
        async def run():
            src = state._ping_source()
            assert src["kind"] == "direct"

        asyncio.run(run())

    def test_ping_loop_runs_and_records(self, state):
        async def run():
            async def fake_probe(src, host, port):
                import types

                w = types.SimpleNamespace()
                w.close = lambda: None
                w.wait_closed = lambda: None
                r = types.SimpleNamespace()
                return r, w

            state._ping_probe = fake_probe
            state.start_proxy_ping()
            for _ in range(200):
                if state._ping_samples:
                    break
                await asyncio.sleep(0.05)
            assert state._ping_samples, "ping loop produced no samples"
            sample = state._ping_samples[-1]
            assert sample["ok"] is True
            assert sample["latency"] >= 0
            status = state.get_proxy_ping_status()
            assert status["ok_count"] >= 1
            state.stop_proxy_ping()

        asyncio.run(run())
