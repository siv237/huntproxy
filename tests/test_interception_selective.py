"""Selective interception — resource registry, config and DNS resolution."""
import pytest

from hunt import interception_selective as ise
from hunt import interception_reconcile as rec
from hunt.transparent_runner import TransparentRunner


class TestInterceptionConfig:
    def test_defaults(self, state):
        cfg = ise.get_config(state)
        assert cfg["selective_enabled"] is False
        assert cfg["drop_quic"] is True
        assert cfg["iface"] == ""
        assert cfg["fallback_direct"] is True
        assert "ports" not in cfg
        assert "auto_detect" not in cfg

    def test_set_config_sanitizes_iface(self, state):
        assert ise.set_config(state, {"iface": "eth0"})["iface"] == "eth0"
        assert ise.set_config(state, {"iface": "bad iface;rm"})["iface"] == ""
        assert ise.set_config(state, {"iface": "x" * 40})["iface"] == ""

    def test_set_config_toggles(self, state):
        cfg = ise.set_config(state, {"fallback_direct": False})
        assert cfg["fallback_direct"] is False
        assert ise.get_config(state)["fallback_direct"] is False

    def test_set_config_sanitizes_iface(self, state):
        assert ise.set_config(state, {"iface": "eth0"})["iface"] == "eth0"
        assert ise.set_config(state, {"iface": "bad iface;rm"})["iface"] == ""
        assert ise.set_config(state, {"iface": "x" * 40})["iface"] == ""

    def test_set_config_clamps_interval(self, state):
        assert ise.set_config(state, {"resolve_interval_sec": 1})["resolve_interval_sec"] == 30
        assert ise.set_config(state, {"resolve_interval_sec": 10 ** 9})["resolve_interval_sec"] == 86400


class TestNormalizeAddress:
    @pytest.mark.parametrize("raw,expected", [
        ("HTTPS://Example.COM/path", "example.com"),
        ("*.youtube.com", "*.youtube.com"),
        (".foo.bar.", "foo.bar"),
        ("1.2.3.4:8080", "1.2.3.4"),
        ("   ", ""),
    ])
    def test_normalize(self, raw, expected):
        assert ise.normalize_address(raw) == expected


class TestResolveSync:
    def test_ip_literal(self):
        ips, status, error = ise.resolve_sync("1.2.3.4")
        assert (ips, status) == (["1.2.3.4"], "ok")
        assert error == ""

    def test_ipv6_rejected(self):
        ips, status, _ = ise.resolve_sync("2001:db8::1")
        assert ips == []
        assert status == "error"

    def test_invalid_domain(self):
        ips, status, error = ise.resolve_sync("this-domain-does-not-exist.invalid")
        assert ips == []
        assert status == "error"
        assert error


class TestResourceCrud:
    def test_create_list_toggle_delete(self, state):
        res = ise.create_resource(state, {
            "name": "YouTube",
            "addresses": ["youtube.com", "*.googlevideo.com", "1.1.1.1"],
        })
        assert res and res["name"] == "YouTube"
        assert res["enabled"] is True
        assert res["auto"] is True
        assert res["ports"] == ""
        assert len(res["entries"]) == 3

        listed = ise.list_resources(state)
        assert len(listed) == 1

        toggled = ise.toggle_resource(state, res["id"])
        assert toggled["enabled"] is False

        updated = ise.update_resource(state, res["id"], {"name": "YT", "addresses": ["8.8.8.8"]})
        assert updated["name"] == "YT"
        assert [e["address"] for e in updated["entries"]] == ["8.8.8.8"]

        assert ise.delete_resource(state, res["id"]) is True
        assert ise.list_resources(state) == []

    def test_create_requires_name(self, state):
        assert ise.create_resource(state, {"addresses": ["x.com"]}) is None

    def test_dedup_addresses(self, state):
        res = ise.create_resource(state, {"name": "dup", "addresses": ["a.com", "A.com", "a.com"]})
        assert len(res["entries"]) == 1

    def test_manual_ports(self, state):
        res = ise.create_resource(state, {
            "name": "svc", "addresses": ["1.2.3.4"], "auto": False, "ports": "8080, 443,x,70000",
        })
        assert res["auto"] is False
        assert res["ports"] == "8080,443"
        assert res["port_list"] == [8080, 443]

    def test_update_switches_to_manual(self, state):
        res = ise.create_resource(state, {"name": "x", "addresses": ["a.com"]})
        upd = ise.update_resource(state, res["id"], {"auto": False, "ports": "8443"})
        assert upd["auto"] is False
        assert upd["ports"] == "8443"


class TestPolicySpec:
    @pytest.mark.asyncio
    async def test_auto_and_manual(self, state, monkeypatch, tmp_path):
        monkeypatch.setattr(ise, "resolve_sync", lambda addr: (["10.0.0.1"], "ok", ""))

        auto = ise.create_resource(state, {"name": "a", "addresses": ["a.com"], "auto": True})
        manual = ise.create_resource(state, {"name": "m", "addresses": ["b.com"], "auto": False, "ports": "8080"})
        await ise.resolve_resource(state, auto["id"])
        await ise.resolve_resource(state, manual["id"])

        assert ise.auto_addresses(state) == ["10.0.0.1"]
        assert ise.active_addresses(state) == ["10.0.0.1"]

        spec = tmp_path / "spec.txt"
        assert ise.write_ipset_spec(state, spec) == 2
        text = spec.read_text()
        assert "auto\t10.0.0.1" in text
        assert "8080\t10.0.0.1" in text

    @pytest.mark.asyncio
    async def test_disabled_resource_excluded(self, state, monkeypatch, tmp_path):
        monkeypatch.setattr(ise, "resolve_sync", lambda addr: (["10.0.0.2"], "ok", ""))
        res = ise.create_resource(state, {"name": "off", "addresses": ["c.com"]})
        await ise.resolve_resource(state, res["id"])
        ise.toggle_resource(state, res["id"])
        assert ise.auto_addresses(state) == []
        assert ise.write_ipset_spec(state, tmp_path / "s.txt") == 0


class TestActualState:
    @pytest.mark.asyncio
    async def test_returns_structure(self):
        result = await rec.actual_state()
        for key in ("available", "selective_chain", "selective_jump", "root"):
            assert key in result


class TestTransportDetect:
    def test_to_absolute_uri_relative(self):
        out = TransparentRunner._to_absolute_uri(
            b"GET / HTTP/1.1\r\nHost: 2ip.io\r\n\r\n", "2ip.io", 80)
        assert out.startswith(b"GET http://2ip.io/ HTTP/1.1")
        assert b"Connection: close" in out

    def test_to_absolute_uri_keeps_absolute(self):
        out = TransparentRunner._to_absolute_uri(
            b"GET http://x.test/y HTTP/1.1\r\n\r\n", "x.test", 80)
        assert out.startswith(b"GET http://x.test/y HTTP/1.1")

    def test_to_absolute_uri_nonstandard_port(self):
        out = TransparentRunner._to_absolute_uri(
            b"GET /p HTTP/1.1\r\n\r\n", "h.test", 8080)
        assert b"http://h.test:8080/p" in out

    @pytest.mark.asyncio
    async def test_peek_tls(self):
        reader = _reader(b"\x16\x03\x01\x00")
        kind, buffered = await TransparentRunner._peek_request(reader, timeout=1)
        assert kind == "tls"
        assert buffered == b"\x16"

    @pytest.mark.asyncio
    async def test_peek_http(self):
        reader = _reader(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        kind, buffered = await TransparentRunner._peek_request(reader, timeout=1)
        assert kind == "http"
        assert buffered.startswith(b"GET /")

    @pytest.mark.asyncio
    async def test_peek_empty(self):
        reader = _reader(b"")
        kind, buffered = await TransparentRunner._peek_request(reader, timeout=1)
        assert (kind, buffered) == ("empty", b"")


def _reader(data: bytes):
    import asyncio
    reader = asyncio.StreamReader()
    if data:
        reader.feed_data(data)
    reader.feed_eof()
    return reader
