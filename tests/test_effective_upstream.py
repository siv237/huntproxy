"""Effective upstream: topbar badge and switch history.

The topbar badge must show the proxy that ACTUALLY served traffic (the real
pool proxy), and the switch history must show real upstream switches — not
per-domain route changes and not repeated rows of one unchanged proxy.
"""

import asyncio
import time

import pytest

import hunt
from hunt.switch_history import (
    _merge_consecutive,
    effective_from_chain,
    enrich_switch_history,
    record_upstream_switch,
)

from tests.test_api import json_body


def _attach_runner(state, selected=None, direct=False):
    from hunt.proxy_runner import ProxyRunner
    runner = ProxyRunner(state)
    runner.active_proxy_addr = selected
    runner.direct_mode = direct
    state.proxy_runner = runner
    return runner


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


class TestBadgeFollowsServedTraffic:
    """The badge is updated from the traffic-log funnel, i.e. only when a
    request was really relayed — never by a bare connection attempt."""

    def _serve(self, state, upstream, status="ok"):
        state._queue_traffic_log(
            (time.time(), "127.0.0.1", "example.com", status, upstream,
             10, 0, 1.0, "http"))

    def test_pool_served_traffic_sets_badge(self, state):
        self._serve(state, "pool:9.9.9.9:1080")
        assert state._effective_upstream["addr"] == "9.9.9.9:1080"
        assert state._effective_upstream["kind"] == "pool"

    def test_selected_and_fallback_served_traffic(self, state):
        self._serve(state, "proxy:1.1.1.1:1")
        assert state._effective_upstream["kind"] == "select"
        self._serve(state, "proxy:1.1.1.1:1 (fallback→pool) → pool:2.2.2.2:2")
        assert state._effective_upstream["addr"] == "2.2.2.2:2"
        assert state._effective_upstream["kind"] == "fallback"

    def test_failed_row_does_not_touch_badge(self, state):
        self._serve(state, "pool:9.9.9.9:1080")
        self._serve(state, "", status="502 no upstream")
        assert state._effective_upstream["addr"] == "9.9.9.9:1080"

    def test_direct_served_traffic_sets_direct(self, state):
        self._serve(state, "direct")
        assert state._effective_upstream["kind"] == "direct"
        assert state._effective_upstream["addr"] == ""


class TestRecordUpstreamSwitch:
    def test_same_address_kind_flip_is_not_a_switch(self, state):
        record_upstream_switch(state, "1.2.3.4:1080", "select")
        record_upstream_switch(state, "1.2.3.4:1080", "pool")
        assert len(state._proxy_switch_history) == 1
        assert state._proxy_switch_history[-1]["action"] == "pool"

    def test_address_change_records_entry(self, state):
        record_upstream_switch(state, "1.2.3.4:1080", "pool")
        record_upstream_switch(state, "5.6.7.8:1080", "pool")
        assert [e["address"] for e in state._proxy_switch_history] == [
            "1.2.3.4:1080", "5.6.7.8:1080"]

    def test_direct_is_not_recorded(self, state):
        record_upstream_switch(state, "1.2.3.4:1080", "pool")
        record_upstream_switch(state, "", "direct")
        assert len(state._proxy_switch_history) == 1


class TestCurrentPoolUpstream:
    """The badge is pool-only: hard selection, else the pool proxy that
    actually carried traffic; nothing when there is no pool traffic."""

    def test_hard_selection_wins(self, state):
        _rating(state, "5.5.5.5:1080", "IE")
        runner = _attach_runner(state, selected="5.5.5.5:1080")
        state._effective_upstream = {"addr": "1.1.1.1:1080", "kind": "pool", "ts": time.time()}
        assert runner.current_pool_upstream() == {"addr": "5.5.5.5:1080", "kind": "select"}

    def test_fallback_shows_pool_proxy_that_took_over(self, state):
        _rating(state, "5.5.5.5:1080", "IE")
        _rating(state, "1.1.1.1:1080", "NL")
        runner = _attach_runner(state, selected="5.5.5.5:1080")
        state._effective_upstream = {"addr": "1.1.1.1:1080", "kind": "fallback", "ts": time.time()}
        assert runner.current_pool_upstream() == {"addr": "1.1.1.1:1080", "kind": "fallback"}

    def test_auto_mode_shows_pool_carrier(self, state):
        _attach_runner(state)
        state._effective_upstream = {"addr": "9.9.9.9:1080", "kind": "pool", "ts": time.time()}
        assert state.proxy_runner.current_pool_upstream() == {"addr": "9.9.9.9:1080", "kind": "pool"}

    def test_stale_pool_carrier_hides_badge(self, state):
        _attach_runner(state)
        state._effective_upstream = {"addr": "9.9.9.9:1080", "kind": "pool", "ts": time.time() - 3600}
        assert state.proxy_runner.current_pool_upstream() == {}

    def test_direct_mode_shows_nothing(self, state):
        _rating(state, "5.5.5.5:1080", "IE")
        _attach_runner(state, selected="5.5.5.5:1080", direct=True)
        assert state.proxy_runner.current_pool_upstream() == {}

    def test_no_selection_no_traffic_shows_nothing(self, state):
        _attach_runner(state)
        assert state.proxy_runner.current_pool_upstream() == {}


class TestMergeConsecutive:
    def test_same_address_rows_are_merged(self):
        hist = [
            {"ts": 1.0, "action": "select", "address": "1.2.3.4:1080"},
            {"ts": 2.0, "action": "pool", "address": "1.2.3.4:1080"},
            {"ts": 3.0, "action": "select", "address": "1.2.3.4:1080"},
        ]
        merged = _merge_consecutive(hist)
        assert len(merged) == 1
        assert merged[0]["ts"] == 1.0
        assert merged[0]["action"] == "select"

    def test_different_addresses_are_not_merged(self):
        hist = [
            {"ts": 1.0, "action": "pool", "address": "1.2.3.4:1080"},
            {"ts": 2.0, "action": "pool", "address": "5.6.7.8:1080"},
        ]
        assert len(_merge_consecutive(hist)) == 2


class TestEnrichDropsDirectRows:
    def test_direct_entries_are_not_shown_as_switches(self, state):
        state._proxy_switch_history = [
            {"ts": time.time() - 300, "action": "pool", "address": "1.2.3.4:1080"},
            {"ts": time.time() - 200, "action": "direct", "address": ""},
            {"ts": time.time() - 100, "action": "select", "address": "1.2.3.4:1080"},
        ]
        rows = enrich_switch_history(state)
        assert [r["address"] for r in rows] == ["1.2.3.4:1080"]


class TestTrafficAggregation:
    def _log(self, state, ts, upstream, bytes_in):
        conn = state._stats_db()
        conn.execute(
            "INSERT INTO traffic_log (ts, client, target, status, upstream, bytes_in, bytes_out, duration, via) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, "127.0.0.1", "example.com", "ok", upstream, bytes_in, 0, 1.0, "http"))
        conn.commit()
        conn.close()

    def test_same_proxy_route_kinds_are_aggregated(self, state):
        now = time.time()
        state._proxy_switch_history = [
            {"ts": now - 300, "action": "select", "address": "1.2.3.4:1080"},
            {"ts": now - 200, "action": "pool", "address": "1.2.3.4:1080"},
            {"ts": now - 100, "action": "select", "address": "1.2.3.4:1080"},
        ]
        self._log(state, now - 250, "proxy:1.2.3.4:1080", 100)
        self._log(state, now - 150, "pool:1.2.3.4:1080", 50)
        rows = enrich_switch_history(state)
        assert len(rows) == 1
        assert rows[0]["address"] == "1.2.3.4:1080"
        assert rows[0]["bytes"] == 150


class TestSwitchHistoryMigration:
    def test_purges_once_and_sets_marker(self, state):
        state._routing_set("switch_hist_v2", "")
        state._proxy_switch_history = [
            {"ts": 1.0, "action": "pool", "address": "1.2.3.4:1080"}]
        state._migrate_switch_history()
        assert state._proxy_switch_history == []
        assert state._routing_get("switch_hist_v2") == "true"
        state._proxy_switch_history = [
            {"ts": 2.0, "action": "select", "address": "5.6.7.8:1080"}]
        state._migrate_switch_history()
        assert len(state._proxy_switch_history) == 1


class TestPingSourceUsesPoolUpstream:
    def test_hard_selection_is_pinged(self, state):
        _rating(state, "5.5.5.5:1080", "IE")
        _attach_runner(state, selected="5.5.5.5:1080")
        state._effective_upstream = {"addr": "1.1.1.1:1080", "kind": "pool", "ts": time.time()}
        src = state._ping_source()
        assert src["addr"] == "5.5.5.5:1080"
        assert src["upstream_kind"] == "select"

    def test_auto_mode_pings_pool_carrier(self, state):
        _rating(state, "1.1.1.1:1080", "NL")
        _attach_runner(state)
        state._effective_upstream = {"addr": "1.1.1.1:1080", "kind": "pool", "ts": time.time()}
        src = state._ping_source()
        assert src["addr"] == "1.1.1.1:1080"
        assert src["kind"] == "pool"

    def test_nothing_to_show(self, state):
        _attach_runner(state)
        assert state._ping_source()["kind"] == "none"


class TestStatusExposesEffectiveUpstream:
    @pytest.mark.asyncio
    async def test_proxy_status_field(self, http_client):
        resp = await http_client("GET", "/api/proxy/status")
        status, data = json_body(resp)
        assert status == 200
        assert "effective_upstream" in data
        assert isinstance(data["effective_upstream"], dict)
