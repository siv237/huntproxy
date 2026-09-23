"""Effective upstream tracking.

The proxy that actually carries user traffic (an automatic pool pick, a
failover reroute, a manual selection or direct) must be visible in the switch
history and in the topbar ping badge.  Before this, both only ever showed the
manually selected proxy, so pool/failover carriers stayed invisible.
"""

import asyncio
import time

import pytest

import hunt
from hunt.proxy_routing import ProxyRouteMixin
from hunt.switch_history import effective_from_chain, record_effective_upstream

from tests.test_api import json_body


class _Engine(ProxyRouteMixin):
    def __init__(self, state, result=None, chain=None):
        self.state = state
        self._result = result
        self._chain = chain or []

    async def _connect_by_route(self, route, host, port, chain, need_connect):
        chain.extend(self._chain)
        return self._result


def _rating(state, addr, cc="NL"):
    r = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1,
                         checks_ok=1, egress_country_code=cc)
    state.ratings[addr] = r
    return r


class TestChainMapping:
    @pytest.mark.parametrize("chain,expect", [
        (["pool:1.2.3.4:1080"], ("1.2.3.4:1080", "pool")),
        (["proxy:1.2.3.4:1080 (fallback→pool)", "pool:5.6.7.8:1080"],
         ("5.6.7.8:1080", "fallback")),
        (["proxy:1.2.3.4:1080"], ("1.2.3.4:1080", "select")),
        (["proxy:1.2.3.4:1080 (retry:1)"], ("1.2.3.4:1080", "select")),
        (["direct"], ("", "direct")),
        (["direct via channel"], ("", "direct")),
        ([], ("", "")),
    ])
    def test_effective_from_chain(self, chain, expect):
        assert effective_from_chain(chain) == expect


class TestRecordEffectiveUpstream:
    def test_records_and_dedups_same_carrier(self, state):
        record_effective_upstream(state, "1.2.3.4:1080", "pool")
        assert state._effective_upstream["addr"] == "1.2.3.4:1080"
        assert state._effective_upstream["kind"] == "pool"
        assert len(state._proxy_switch_history) == 1
        assert state._proxy_switch_history[-1]["action"] == "pool"
        record_effective_upstream(state, "1.2.3.4:1080", "pool")
        assert len(state._proxy_switch_history) == 1

    def test_kind_change_records_new_entry(self, state):
        record_effective_upstream(state, "1.2.3.4:1080", "pool")
        record_effective_upstream(state, "1.2.3.4:1080", "fallback")
        assert [e["action"] for e in state._proxy_switch_history] == ["pool", "fallback"]

    def test_unknown_kind_ignored(self, state):
        record_effective_upstream(state, "1.2.3.4:1080", "bogus")
        assert state._proxy_switch_history == []
        assert state._effective_upstream["addr"] == ""


class TestConnectUpstreamRecords:
    def test_pool_pick_recorded(self, state):
        async def run():
            engine = _Engine(state, result=(object(), object(), False),
                             chain=["pool:9.9.9.9:1080"])
            assert await engine._connect_upstream("example.com", 80) is not None
            assert state._effective_upstream["kind"] == "pool"
            assert state._effective_upstream["addr"] == "9.9.9.9:1080"
            assert state._proxy_switch_history[-1]["action"] == "pool"

        asyncio.run(run())

    def test_failover_recorded_as_fallback(self, state):
        async def run():
            engine = _Engine(
                state, result=(object(), object(), False),
                chain=["proxy:1.1.1.1:1 (fallback→pool)", "pool:2.2.2.2:2"])
            await engine._connect_upstream("example.com", 80)
            assert state._effective_upstream["kind"] == "fallback"
            assert state._effective_upstream["addr"] == "2.2.2.2:2"

        asyncio.run(run())

    def test_manual_selection_recorded_as_select(self, state):
        async def run():
            engine = _Engine(state, result=(object(), object(), False),
                             chain=["proxy:1.1.1.1:1"])
            await engine._connect_upstream("example.com", 80)
            assert state._effective_upstream["kind"] == "select"

        asyncio.run(run())

    def test_failed_connection_records_nothing(self, state):
        async def run():
            engine = _Engine(state, result=None)
            assert await engine._connect_upstream("example.com", 80) is None
            assert state._proxy_switch_history == []
            assert state._effective_upstream["addr"] == ""

        asyncio.run(run())


class TestPingSourceUsesEffectiveUpstream:
    def test_prefers_effective_over_selected(self, state):
        _rating(state, "5.5.5.5:1080", "IE")
        _rating(state, "1.1.1.1:1080", "NL")
        state._proxy_active_addr = "5.5.5.5:1080"
        state._effective_upstream = {"addr": "1.1.1.1:1080", "kind": "pool", "ts": time.time()}
        src = state._ping_source()
        assert src["addr"] == "1.1.1.1:1080"
        assert src["upstream_kind"] == "pool"
        assert src["kind"] == "pool"

    def test_falls_back_to_selected_without_effective(self, state):
        _rating(state, "5.5.5.5:1080", "IE")
        state._proxy_active_addr = "5.5.5.5:1080"
        src = state._ping_source()
        assert src["addr"] == "5.5.5.5:1080"
        assert src["kind"] == "pool"

    def test_direct_when_nothing_effective_or_selected(self, state):
        src = state._ping_source()
        assert src["kind"] == "direct"
        assert src["addr"] == ""


class TestStatusExposesEffectiveUpstream:
    @pytest.mark.asyncio
    async def test_proxy_status_field(self, http_client):
        resp = await http_client("GET", "/api/proxy/status")
        status, data = json_body(resp)
        assert status == 200
        assert "effective_upstream" in data
        assert isinstance(data["effective_upstream"], dict)
