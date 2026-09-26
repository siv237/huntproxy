"""Proxy ping module — source resolution and status API shape."""

import asyncio
import json

from hunt.proxy_runner import ProxyRunner
from hunt.scheduler import SchedulerEngine
from hunt.task_executor import TaskExecutor


def _attach_runner(state, selected=None, direct=False):
    runner = ProxyRunner(state)
    runner.active_proxy_addr = selected
    runner.direct_mode = direct
    state.proxy_runner = runner
    return runner


class TestProxyPingStatus:
    async def _status(self, state):
        return state.get_proxy_ping_status()

    def test_status_shape_without_proxy(self, state):
        async def run():
            status = await self._status(state)
            assert status["source"] in ("pool", "direct", "none")
            assert status["window"] == 60
            assert status["interval"] == 1.0
            assert isinstance(status["samples"], list)
            assert isinstance(status["last"], dict)
            assert "latency" in status["last"]
            assert isinstance(status["geo"], dict)
            assert status["channel"] is None

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
            state.ratings["1.2.3.4:8080"] = state._create_rating("1.2.3.4:8080", "RU", "ru")
            _attach_runner(state, selected="1.2.3.4:8080")
            src = state._ping_source()
            assert src["kind"] == "pool"
            assert src["addr"] == "1.2.3.4:8080"
            assert src["host"] == "1.2.3.4"
            assert src["port"] == 8080

        asyncio.run(run())

    def test_ping_source_none_without_pool(self, state):
        async def run():
            _attach_runner(state)
            assert state._ping_source()["kind"] == "none"

        asyncio.run(run())

    def test_primary_stays_on_pool_when_channel_set(self, state):
        """The badge must show the client-path proxy, not the engine channel."""
        async def run():
            state.ratings["1.2.3.4:8080"] = state._create_rating("1.2.3.4:8080", "RU", "ru")
            state.ratings["5.6.7.8:1080"] = state._create_rating("5.6.7.8:1080", "US", "us")
            _attach_runner(state, selected="1.2.3.4:8080")
            state.set_channel("proxy:5.6.7.8:1080")
            src = state._ping_source()
            assert src["kind"] == "pool"
            assert src["addr"] == "1.2.3.4:8080"
            chsrc = state._ping_channel_source()
            assert chsrc["addr"] == "5.6.7.8:1080"
            status = state.get_proxy_ping_status()
            assert status["source"] == "pool"
            assert status["channel"] is not None
            assert status["channel"]["addr"] == "5.6.7.8:1080"

        asyncio.run(run())

    def test_channel_ping_source_none_without_channel(self, state):
        async def run():
            assert state._ping_channel_source() is None
            assert state.get_proxy_ping_status()["channel"] is None

        asyncio.run(run())

    def test_channel_ping_loop_records(self, state):
        async def run():
            import types

            state.ratings["5.6.7.8:1080"] = state._create_rating("5.6.7.8:1080", "US", "us")
            state.set_channel("proxy:5.6.7.8:1080")

            def _conn():
                w = types.SimpleNamespace()
                w.close = lambda: None
                w.wait_closed = lambda: None
                return types.SimpleNamespace(), w

            async def fake_probe(src, host, port):
                return _conn()

            async def fake_outbound(host, port, **kw):
                return _conn()

            state._ping_probe = fake_probe
            state._outbound_connect = fake_outbound
            state.start_proxy_ping()
            for _ in range(200):
                if state._ping_channel_samples:
                    break
                await asyncio.sleep(0.05)
            assert state._ping_channel_samples, "channel ping produced no samples"
            assert state._ping_channel_last["ok"] is True
            status = state.get_proxy_ping_status()
            assert status["channel"]["ok_count"] >= 1
            state.stop_proxy_ping()

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
            state.ratings["1.2.3.4:8080"] = state._create_rating("1.2.3.4:8080", "RU", "ru")
            _attach_runner(state, selected="1.2.3.4:8080")
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
