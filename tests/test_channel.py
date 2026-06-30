"""Tests for the channel (engine outbound proxy) feature."""
import asyncio
import json
import struct

import pytest

import hunt


class FakeSocks5Proxy:
    """A minimal SOCKS5 proxy that records the target and tunnels traffic."""

    def __init__(self, target_host, target_port, target_handler):
        self.target_host = target_host
        self.target_port = target_port
        self.target_handler = target_handler
        self.host = "127.0.0.1"
        self.port = 0
        self.server = None
        self.connected_targets = []

    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle(self, reader, writer):
        try:
            # SOCKS5 greeting
            greeting = await reader.readexactly(2)
            assert greeting[0] == 5
            nmethods = greeting[1]
            await reader.readexactly(nmethods)
            writer.write(bytes([5, 0]))  # no auth
            await writer.drain()
            # request
            hdr = await reader.readexactly(4)
            assert hdr[0] == 5 and hdr[1] == 1
            atyp = hdr[3]
            if atyp == 1:
                addr_bytes = await reader.readexactly(4)
                host = ".".join(str(b) for b in addr_bytes)
            elif atyp == 3:
                dl = (await reader.readexactly(1))[0]
                host = (await reader.readexactly(dl)).decode()
            else:
                writer.close()
                return
            port = struct.unpack(">H", await reader.readexactly(2))[0]
            self.connected_targets.append((host, port))
            writer.write(bytes([5, 0, 0, 1, 127, 0, 0, 1, 0, 0]))
            await writer.drain()
            # Now tunnel: pipe target_handler over reader/writer
            await self.target_handler(reader, writer)
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


class TestChannelLogic:
    def test_default_channel_is_direct(self, state):
        assert state._resolve_channel() == ""
        assert state._channel_curl_proxy() == ""
        st = state.get_channel_status()
        assert st["channel_route"] == ""
        assert st["proxy"] is None
        assert "curl_proxy" not in st  # credentials must not leak via status

    def test_set_channel_custom_persists(self, state):
        # create a custom proxy
        state.create_custom_proxy({
            "id": "testchan", "name": "Test Channel",
            "protocol": "socks5", "host": "127.0.0.1", "port": 1080,
        })
        state.set_channel("custom:testchan")
        assert state._channel_route == "custom:testchan"
        st = state.get_channel_status()
        assert st["proxy"]["host"] == "127.0.0.1"
        assert st["proxy"]["port"] == 1080
        assert st["available"] is True
        # curl string uses socks5h for DNS-over-proxy
        assert state._channel_curl_proxy() == "socks5h://127.0.0.1:1080"
        # status must never embed credentials
        assert "curl_proxy" not in st

    def test_set_channel_direct_clears(self, state):
        state.set_channel("custom:whatever")
        state.set_channel("")
        assert state._channel_route == ""
        assert state._channel_curl_proxy() == ""

    def test_pool_route_rejected_for_engine(self, state):
        state.set_channel("pool")
        assert state._channel_route == ""
        assert state._resolve_channel() == ""

    def test_channel_proxy_missing_custom_returns_none(self, state):
        assert state._channel_proxy("custom:nonexistent") is None

    def test_outbound_fail_closed_when_channel_unresolvable(self, state):
        """A selected but unresolvable channel must NOT fall back to direct."""
        state.set_channel("custom:nonexistent")
        assert state._channel_is_set() is True

        async def run():
            server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            try:
                with pytest.raises(OSError):
                    await state._outbound_connect("127.0.0.1", port, timeout=2)
            finally:
                server.close()
                await server.wait_closed()

        asyncio.run(run())

    def test_channel_proxy_disabled_custom_returns_none(self, state):
        state.create_custom_proxy({
            "id": "dis", "name": "Disabled", "protocol": "socks5",
            "host": "127.0.0.1", "port": 1080,
        })
        state.update_custom_proxy("dis", {"enabled": False})
        assert state._channel_proxy("custom:dis") is None

    def test_channel_proxy_proxy_route_blacklisted(self, state):
        state.blacklist["1.2.3.4:8080"] = "test"
        assert state._channel_proxy("proxy:1.2.3.4:8080") is None

    def test_channel_curl_proxy_http_with_auth(self, state):
        state.create_custom_proxy({
            "id": "auth", "name": "Auth", "protocol": "http",
            "host": "10.0.0.1", "port": 8080,
            "username": "u", "password": "p@ss",
        })
        state.set_channel("custom:auth")
        curl = state._channel_curl_proxy()
        assert curl.startswith("http://")
        assert "10.0.0.1:8080" in curl
        assert "u:p%40ss@" in curl

    def test_channel_status_after_reload(self, tmp_data_dir, empty_config):
        s1 = hunt.HuntState(empty_config)
        s1.create_custom_proxy({
            "id": "persist", "name": "Persist", "protocol": "socks5",
            "host": "127.0.0.1", "port": 1080,
        })
        s1.set_channel("custom:persist")
        s1._save_state()
        s2 = hunt.HuntState(empty_config)
        assert s2._channel_route == "custom:persist"
        assert s2._channel_curl_proxy() == "socks5h://127.0.0.1:1080"


class TestOutboundConnect:
    def test_outbound_connect_direct(self, state):
        """Without a channel, _outbound_connect behaves like open_connection."""

        async def echo_handler(reader, writer):
            data = await reader.readexactly(4)
            writer.write(data)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        async def run():
            server = await asyncio.start_server(echo_handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            try:
                r, w = await state._outbound_connect("127.0.0.1", port, timeout=5)
                w.write(b"ping")
                await w.drain()
                data = await r.readexactly(4)
                assert data == b"ping"
                w.close()
                await w.wait_closed()
            finally:
                server.close()
                await server.wait_closed()

        asyncio.run(run())

    def test_outbound_connect_via_socks5_channel(self, state):
        """With a SOCKS5 channel, _outbound_connect tunnels through it."""

        async def target_handler(reader, writer):
            data = await reader.readexactly(4)
            writer.write(b"pong")
            await writer.drain()

        proxy = FakeSocks5Proxy("127.0.0.1", 0, target_handler)

        async def run():
            await proxy.start()
            try:
                # register the proxy as a custom proxy and select it as channel
                state.create_custom_proxy({
                    "id": "s5", "name": "S5 Channel", "protocol": "socks5",
                    "host": "127.0.0.1", "port": proxy.port,
                })
                state.set_channel("custom:s5")

                # _outbound_connect to a fake target; the proxy will record it
                r, w = await state._outbound_connect("93.184.216.34", 80, timeout=8)
                w.write(b"ping")
                await w.drain()
                data = await r.readexactly(4)
                assert data == b"pong"
                w.close()
                await w.wait_closed()
                # the proxy should have tunneled to the requested target
                assert len(proxy.connected_targets) == 1
                assert proxy.connected_targets[0] == ("93.184.216.34", 80)
            finally:
                await proxy.stop()

        asyncio.run(run())


class TestChannelAPI:
    def test_channel_status_endpoint(self, http_client):
        async def run():
            resp = await http_client("GET", "/api/channel/status")
            body, status = _parse(resp)
            assert status == 200
            assert body["channel_route"] == ""

        asyncio.run(run())

    def test_channel_select_endpoint(self, http_client):
        async def run():
            resp = await http_client("POST", "/api/channel/select?route=custom:apitest")
            body, status = _parse(resp)
            assert status == 200
            assert body["channel_route"] == "custom:apitest"

            resp2 = await http_client("GET", "/api/channel/status")
            body2, _ = _parse(resp2)
            assert body2["channel_route"] == "custom:apitest"

            # cleanup
            await http_client("POST", "/api/channel/select?route=")

        asyncio.run(run())

    def test_canary_status_includes_channel(self, http_client):
        async def run():
            resp = await http_client("GET", "/api/canary/status")
            body, status = _parse(resp)
            assert status == 200
            assert "channel" in body
            assert "channel_route" in body["channel"]

        asyncio.run(run())


def _parse(resp_bytes):
    text = resp_bytes.decode(errors="replace")
    head, _, body = text.partition("\r\n\r\n")
    status_line = head.split("\r\n")[0]
    status = int(status_line.split()[1])
    return json.loads(body), status
