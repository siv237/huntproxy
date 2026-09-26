"""Live traffic counters for the topbar speed.

The rate must move WHILE a transfer is in flight: request rows reach the DB
only when the request finishes (and are written in batches), so the speed used
to read 0 almost always and spike once per flush.
"""

import asyncio
import time

import hunt
from hunt.proxy_runner import ProxyRunner


class _FakeReader:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _n):
        await asyncio.sleep(0)
        return self._chunks.pop(0) if self._chunks else b""


class _FakeWriter:
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data

    async def drain(self):
        return None

    def close(self):
        return None


class TestLiveByteCounters:
    def test_relay_bumps_live_counters(self, state):
        runner = ProxyRunner(state)

        async def run():
            client_reader = _FakeReader([b"abc", b""])
            upstream_reader = _FakeReader([b"defgh", b""])
            bi, bo = await runner._relay(client_reader, _FakeWriter(),
                                         upstream_reader, _FakeWriter())
            assert bi == 3 and bo == 5
            assert state._live_bytes_in == 3
            assert state._live_bytes_out == 5

        asyncio.run(run())

    def test_counters_are_monotonic_across_requests(self, state):
        runner = ProxyRunner(state)

        async def run():
            await runner._relay(_FakeReader([b"ab", b""]), _FakeWriter(),
                                _FakeReader([b"c", b""]), _FakeWriter())
            await runner._relay(_FakeReader([b"abcd", b""]), _FakeWriter(),
                                _FakeReader([b"", b""]), _FakeWriter())
            assert state._live_bytes_in == 6
            assert state._live_bytes_out == 1

        asyncio.run(run())


class TestGetLiveTraffic:
    def test_returns_live_counters_and_rollup_total(self, state):
        state._live_bytes_in = 111
        state._live_bytes_out = 222
        state._queue_traffic_log(
            (time.time(), "127.0.0.1", "example.com", "ok",
             "pool:9.9.9.9:1080", 500, 700, 1.0, "http"))
        payload = state.get_live_traffic()
        assert payload["live_in_bytes"] == 111
        assert payload["live_out_bytes"] == 222
        assert payload["total_bytes"] >= 1200

    def test_zeroes_before_any_traffic(self, state):
        payload = state.get_live_traffic()
        assert payload["live_in_bytes"] == 0
        assert payload["live_out_bytes"] == 0
