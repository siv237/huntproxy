import json

import pytest

from hunt.pac import render_pac
from tests.test_api import parse_response, json_body


class TestRenderPac:
    def test_direct_hosts_and_internal_nets(self):
        pac = render_pac({
            "proxy_host": "192.168.1.5",
            "proxy_port": 17277,
            "direct_hosts": ["*.dgk.ru", "example.com"],
            "internal_nets": [{"network": "10.0.0.0", "mask": "255.0.0.0"}],
        })
        assert "function FindProxyForURL(url, host)" in pac
        assert "shExpMatch(host, directHosts[i])" in pac
        assert "*.dgk.ru" in pac
        assert '"example.com"' in pac
        assert "isInNet(dnsResolve(host), internalNets[j].network, internalNets[j].mask)" in pac
        assert "isPlainHostName(host)" in pac
        assert "return \"PROXY 192.168.1.5:17277\";" in pac

    def test_empty_proxy_returns_direct(self):
        pac = render_pac({
            "proxy_host": "",
            "proxy_port": 0,
            "direct_hosts": [],
            "internal_nets": [],
        })
        assert "return \"DIRECT\";" in pac

    def test_failover_proxies(self):
        pac = render_pac({
            "proxies": [{"host": "a", "port": 1}, {"host": "b", "port": 2}],
        })
        assert 'return "PROXY a:1; PROXY b:2";' in pac

    def test_json_serialization_is_inline(self):
        pac = render_pac({
            "proxy_host": "h",
            "proxy_port": 8080,
            "direct_hosts": ["x", "y"],
            "internal_nets": [{"network": "172.16.0.0", "mask": "255.240.0.0"}],
        })
        assert "[\"x\", \"y\"]" in pac
        assert '"network": "172.16.0.0"' in pac


class TestPacApi:
    async def test_pac_js_disabled_returns_503(self, http_client):
        resp = await http_client("GET", "/pac.js")
        status, _, body = parse_response(resp)
        assert status == 503

    async def test_pac_config_empty_state(self, http_client):
        resp = await http_client("GET", "/api/pac/config")
        status, data = json_body(resp)
        assert status == 200
        for key in ("enabled", "proxy_host", "proxy_port", "direct_hosts",
                    "internal_nets", "url", "preview"):
            assert key in data
        assert data["direct_hosts"] == []
        assert data["internal_nets"] == []

    async def test_enable_and_save(self, http_client):
        resp = await http_client("POST", "/api/pac/config", body=json.dumps({
            "enabled": True,
            "proxy_host": "192.168.1.5",
            "proxy_port": 17277,
            "direct_hosts": ["*.dgk.ru"],
            "internal_nets": [{"network": "10.0.0.0", "mask": "255.0.0.0"}],
        }))
        status, data = json_body(resp)
        assert status == 200
        assert data["enabled"] is True
        assert data["proxy_host"] == "192.168.1.5"
        assert "*.dgk.ru" in data["direct_hosts"]
        assert data["internal_nets"] == [{"network": "10.0.0.0", "mask": "255.0.0.0"}]
        assert "shExpMatch" in data["preview"]

    async def test_pac_js_served_when_enabled(self, http_client):
        await http_client("POST", "/api/pac/config", body=json.dumps({
            "enabled": True, "proxy_host": "192.168.1.5", "proxy_port": 17277,
        }))
        resp = await http_client("GET", "/pac.js")
        status, headers, body = parse_response(resp)
        assert status == 200
        assert "proxy-autoconfig" in headers.get("content-type", "")
        assert "FindProxyForURL" in body.decode()
        assert "PROXY 192.168.1.5:17277" in body.decode()

    async def test_pac_js_reflects_exception(self, http_client):
        await http_client("POST", "/api/pac/config", body=json.dumps({
            "enabled": True,
            "proxy_host": "192.168.1.5",
            "proxy_port": 17277,
            "direct_hosts": ["blocked.example"],
        }))
        resp = await http_client("GET", "/pac.js")
        _, _, body = parse_response(resp)
        assert "blocked.example" in body.decode()

    async def test_detect_ip(self, http_client):
        resp = await http_client("POST", "/api/pac/detect-ip")
        status, data = json_body(resp)
        assert status == 200
        assert data["ip"]

    async def test_list_local_ips(self, http_client):
        resp = await http_client("GET", "/api/pac/ips")
        status, data = json_body(resp)
        assert status == 200
        assert isinstance(data["ips"], list)
        assert len(data["ips"]) >= 1
        assert "127.0.0.1" in data["ips"]
