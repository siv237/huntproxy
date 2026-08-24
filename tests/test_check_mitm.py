import asyncio

import pytest

from hunt.check_mitm import CheckMitmMixin, MITM_TEST_HOSTS


class _Engine(CheckMitmMixin):
    """Bare mixin host with scripted tunnel/TLS verdicts per target."""

    def __init__(self, tunnels=None, verdicts=None):
        self.mitm_hosts = ["a.test", "b.test", "c.test"]
        self.effective_timeout = 5
        self.tunnels = dict(tunnels or {})
        self.verdicts = dict(verdicts or {})
        self.probed = []
        self.tunnel_calls = 0

    async def _tunnel_to(self, r, w, host, proto):
        self.tunnel_calls += 1
        self.probed.append(host)
        return self.tunnels.get(host, False)

    async def _check_mitm_tls_over(self, w, server_hostname):
        return self.verdicts.get(server_hostname)

    def _channel_is_set(self):
        return False


def _run(engine):
    async def go():
        return await engine._check_mitm_via(None, None, 8080, is_socks=False)
    return asyncio.run(go())


class TestCheckMitmVia:
    def test_clean_on_first_target_short_circuits(self):
        e = _Engine(
            tunnels={"a.test": True},
            verdicts={"a.test": "clean"},
        )
        connect_ok, mitm = _run(e)
        assert connect_ok is True
        assert mitm is False
        assert e.probed == ["a.test"]

    def test_bad_then_clean_is_not_mitm(self):
        e = _Engine(
            tunnels={"a.test": True, "b.test": True},
            verdicts={"a.test": "mitm", "b.test": "clean"},
        )
        connect_ok, mitm = _run(e)
        assert connect_ok is True
        assert mitm is False

    def test_single_target_failure_stays_inconclusive(self):
        e = _Engine(
            tunnels={"a.test": True},
            verdicts={"a.test": "mitm"},
        )
        connect_ok, mitm = _run(e)
        assert connect_ok is True
        assert mitm is False

    def test_two_confirmed_failures_flag_mitm(self):
        e = _Engine(
            tunnels={"a.test": True, "b.test": True},
            verdicts={"a.test": "mitm", "b.test": "mitm"},
        )
        connect_ok, mitm = _run(e)
        assert connect_ok is True
        assert mitm is True

    def test_inconclusive_handshake_never_flags(self):
        e = _Engine(
            tunnels={"a.test": True, "b.test": True},
            verdicts={"a.test": None, "b.test": None},
        )
        connect_ok, mitm = _run(e)
        assert connect_ok is True
        assert mitm is False

    def test_all_targets_unreachable_fails_check(self):
        e = _Engine()
        connect_ok, mitm = _run(e)
        assert connect_ok is False
        assert mitm is False
        assert len(e.probed) == 3

    def test_proto_selection_by_port(self):
        assert CheckMitmMixin._mitm_proto(4145, True) == "socks4"
        assert CheckMitmMixin._mitm_proto(1080, True) == "socks5"
        assert CheckMitmMixin._mitm_proto(8080, False) == "http"

    def test_default_hosts_used_when_unconfigured(self):
        e = _Engine()
        del e.mitm_hosts
        assert e._mitm_hosts() == list(MITM_TEST_HOSTS)

    def test_channel_baseline_unset_is_trusted(self):
        e = _Engine()
        assert e._channel_is_set() is False
        assert asyncio.run(e._channel_tls_baseline_trusted()) is True
