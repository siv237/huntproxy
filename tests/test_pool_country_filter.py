"""Pool country filter — automatic pool selection and failover reroute.

The filter restricts which exit countries the automatic pool may use; manual
selection of a concrete proxy must stay possible (covered by _build_pool only
being consulted for pool/failover routes).
"""

import asyncio
import json

import pytest

import hunt
from hunt.proxy_routing import ProxyRouteMixin

from tests.test_api import json_body


class _PoolEngine(ProxyRouteMixin):
    def __init__(self, state):
        self.state = state


def _add(state, addr: str, cc: str, status: str = "ok"):
    r = hunt.ProxyRating(address=addr, last_status=status, checks_total=1,
                         checks_ok=1, egress_country_code=cc)
    state.ratings[addr] = r
    return r


def _pool(state, need_connect: bool = False):
    return [r.address for r in _PoolEngine(state)._build_pool(need_connect)]


class TestPoolCountryPolicyStorage:
    def test_default_is_off(self, state):
        assert state.get_pool_country_policy() == {"mode": "off", "countries": []}

    def test_set_normalizes_codes_and_mode(self, state):
        policy = state.set_pool_country_policy("only", ["nl", "DE", "usa", "x", ""])
        assert policy["mode"] == "only"
        assert policy["countries"] == ["DE", "NL"]
        assert policy["persisted"] is True
        assert state.get_pool_country_policy() == {"mode": "only", "countries": ["DE", "NL"]}

    def test_invalid_mode_falls_back_to_off(self, state):
        assert state.set_pool_country_policy("bogus", ["NL"])["mode"] == "off"

    def test_persisted_across_reads(self, state):
        result = state.set_pool_country_policy("exclude", ["RU"])
        assert result["persisted"] is True
        assert json.loads(state._routing_get("pool_country_policy"))["mode"] == "exclude"
        assert state.get_pool_country_policy()["countries"] == ["RU"]


class TestPoolCountryAllows:
    @pytest.mark.parametrize("mode,code,allowed", [
        ("only", "NL", True),
        ("only", "ru", True),
        ("only", "de", False),
        ("only", "", False),
        ("exclude", "RU", False),
        ("exclude", "de", True),
        ("exclude", "", True),
    ])
    def test_predicate(self, state, mode, code, allowed):
        state.set_pool_country_policy(mode, ["NL", "RU"])
        assert state.pool_country_allows(code) is allowed

    def test_off_allows_everything(self, state):
        state.set_pool_country_policy("off", ["RU"])
        assert state.pool_country_allows("RU") is True
        assert state.pool_country_allows("") is True

    def test_empty_list_allows_everything(self, state):
        state.set_pool_country_policy("only", [])
        assert state.pool_country_allows("NL") is True


class TestBuildPoolCountryFilter:
    def test_off_keeps_all(self, state):
        _add(state, "1.1.1.1:1", "NL")
        _add(state, "2.2.2.2:2", "RU")
        _add(state, "3.3.3.3:3", "")
        assert set(_pool(state)) == {"1.1.1.1:1", "2.2.2.2:2", "3.3.3.3:3"}

    def test_only_keeps_listed_countries(self, state):
        _add(state, "1.1.1.1:1", "NL")
        _add(state, "2.2.2.2:2", "RU")
        _add(state, "3.3.3.3:3", "")
        state.set_pool_country_policy("only", ["NL"])
        assert _pool(state) == ["1.1.1.1:1"]

    def test_only_drops_unknown_country(self, state):
        _add(state, "3.3.3.3:3", "")
        state.set_pool_country_policy("only", ["NL"])
        assert _pool(state) == []

    def test_exclude_drops_listed_countries(self, state):
        _add(state, "1.1.1.1:1", "NL")
        _add(state, "2.2.2.2:2", "RU")
        _add(state, "3.3.3.3:3", "")
        state.set_pool_country_policy("exclude", ["RU"])
        assert set(_pool(state)) == {"1.1.1.1:1", "3.3.3.3:3"}

    def test_filter_matches_exit_not_listen_country(self, state):
        """A proxy listening in NL but exiting in RU is filtered by RU."""
        r = _add(state, "1.1.1.1:1", "RU")
        r.country_code = "NL"
        state.set_pool_country_policy("exclude", ["RU"])
        assert _pool(state) == []

    def test_grace_proxy_filtered_by_country(self, state):
        """Grace-period proxies are part of the pool and must be filtered too."""
        r = _add(state, "1.1.1.1:1", "RU", status="failed")
        r.speed_count = 1
        r.speed_sum = 120
        r.consecutive_fails = 0
        assert r.in_grace and r.pool_eligible
        state.set_pool_country_policy("exclude", ["RU"])
        assert _pool(state) == []
        state.set_pool_country_policy("off", [])
        assert _pool(state) == ["1.1.1.1:1"]

    def test_country_filter_does_not_run_for_uneligible(self, state):
        """A proxy rejected by pool_eligible is dropped regardless of policy."""
        _add(state, "1.1.1.1:1", "NL", status="failed")
        state.set_pool_country_policy("off", [])
        assert _pool(state) == []


class TestManualSelectionBypassesFilter:
    """Manual selection of a concrete proxy must not be affected by the pool
    country filter — only the automatic pool and the failover reroute are."""

    def _engine_with_stub(self, state, result):
        engine = _PoolEngine(state)
        seen = {}

        async def stub_addr(addr, host, port, chain, need_connect):
            seen["addr"] = addr
            return result

        async def stub_pool(host, port, chain, need_connect):
            seen["pool"] = True
            return ("r", "w", False)

        engine._connect_via_addr = stub_addr
        engine._connect_via_pool = stub_pool
        return engine, seen

    def test_excluded_country_still_selected_manually(self, state):
        _add(state, "1.1.1.1:1", "RU")
        state.set_pool_country_policy("exclude", ["RU"])

        async def run():
            engine, seen = self._engine_with_stub(state, ("r", "w", False))
            result = await engine._connect_by_route("proxy:1.1.1.1:1", "example.com", 443)
            assert result is not None
            assert seen["addr"] == "1.1.1.1:1"
            assert "pool" not in seen

        asyncio.run(run())

    def test_manual_failure_falls_back_to_filtered_pool(self, state):
        _add(state, "1.1.1.1:1", "RU")
        _add(state, "2.2.2.2:2", "NL")
        state.set_pool_country_policy("exclude", ["RU"])
        state.routing_set_fallback(True)

        async def run():
            engine, seen = self._engine_with_stub(state, None)
            result = await engine._connect_by_route("proxy:1.1.1.1:1", "example.com", 443)
            assert result is not None and seen.get("pool") is True
            assert _pool(state) == ["2.2.2.2:2"]

        asyncio.run(run())

    def test_manual_failure_strict_mode_does_not_reach_pool(self, state):
        _add(state, "1.1.1.1:1", "RU")
        state.set_pool_country_policy("exclude", ["RU"])
        state.routing_set_fallback(False)

        async def run():
            engine, seen = self._engine_with_stub(state, None)
            assert await engine._connect_by_route("proxy:1.1.1.1:1", "example.com", 443) is None
            assert "pool" not in seen

        asyncio.run(run())


class TestPoolCountriesAggregation:
    def test_counts_exit_countries(self, state):
        _add(state, "1.1.1.1:1", "NL")
        _add(state, "2.2.2.2:2", "NL")
        _add(state, "3.3.3.3:3", "RU")
        _add(state, "4.4.4.4:4", "")
        result = state.get_pool_countries()
        assert result[0] == {"country_code": "NL", "country": "The Netherlands", "count": 2}
        assert {"country_code": "RU", "country": "Russia", "count": 1} in result
        assert all(item["country_code"] for item in result)

    def test_ignores_non_eligible(self, state):
        _add(state, "1.1.1.1:1", "NL", status="failed")
        assert state.get_pool_countries() == []


class TestPoolCountriesApi:
    @pytest.mark.asyncio
    async def test_roundtrip(self, http_client):
        resp = await http_client("POST", "/api/pool/countries",
                                 {"mode": "only", "countries": ["nl", "DE", "usa"]})
        status, data = json_body(resp)
        assert status == 200
        assert data["mode"] == "only"
        assert data["countries"] == ["DE", "NL"]
        assert isinstance(data["available"], list)
        assert data["warning"] == "no_proxies_in_selected_countries"

        resp = await http_client("GET", "/api/pool/countries")
        status, data = json_body(resp)
        assert status == 200
        assert data["mode"] == "only"
        assert data["countries"] == ["DE", "NL"]
        assert data["warning"] == "no_proxies_in_selected_countries"

        resp = await http_client("POST", "/api/pool/countries", {"mode": "off"})
        status, data = json_body(resp)
        assert status == 200
        assert data["mode"] == "off"
        assert data["warning"] == ""
