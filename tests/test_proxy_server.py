import asyncio
import time
import pytest
import hunt
from hunt import proxy_routing


class TestProxyServer:
    def test_proxy_runner_start_stop(self, state):
        async def run():
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            await runner.start(0)
            assert runner.running is True
            for _ in range(50):
                await asyncio.sleep(0.01)
                if runner._server is not None:
                    break
            assert runner._server is not None
            actual_port = runner._server.sockets[0].getsockname()[1]
            assert actual_port > 0
            await runner.stop()
            assert runner.running is False

        asyncio.run(run())

    def test_socks5_runner_start_stop(self, state):
        async def run():
            runner = hunt.Socks5Runner(state, "127.0.0.1")
            await runner.start(0)
            assert runner.running is True
            for _ in range(50):
                await asyncio.sleep(0.01)
                if runner._server is not None:
                    break
            assert runner._server is not None
            actual_port = runner._server.sockets[0].getsockname()[1]
            assert actual_port > 0
            await runner.stop()
            assert runner.running is False

        asyncio.run(run())

    def test_transparent_runner_start_stop(self, state):
        async def run():
            runner = hunt.TransparentRunner(state, "127.0.0.1")
            await runner.start(0)
            assert runner.running is True
            assert state._transparent_running is True
            for _ in range(50):
                await asyncio.sleep(0.01)
                if runner._server is not None:
                    break
            assert runner._server is not None
            actual_port = runner._server.sockets[0].getsockname()[1]
            assert actual_port > 0
            await runner.stop()
            assert runner.running is False
            assert state._transparent_running is False

        asyncio.run(run())

    def test_proxy_runner_select_sets_active_address(self, state):
        runner = hunt.ProxyRunner(state, "127.0.0.1")
        runner.select("1.2.3.4:8080")
        assert runner.active_proxy_addr == "1.2.3.4:8080"
        assert runner.selected_proxy is not None
        assert runner.selected_proxy.address == "1.2.3.4:8080"

    def test_proxy_runner_direct_mode(self, state):
        runner = hunt.ProxyRunner(state, "127.0.0.1")
        assert runner.direct_mode is False
        runner.direct_mode = True
        assert runner.direct_mode is True

    def test_socks5_runner_selected_proxy_uses_state_runner(self, state):
        state.proxy_runner = hunt.ProxyRunner(state, "127.0.0.1")
        state.proxy_runner.select("1.2.3.4:1080")
        runner = hunt.Socks5Runner(state, "127.0.0.1")
        assert runner.selected_proxy is not None
        assert runner.selected_proxy.address == "1.2.3.4:1080"

    def test_proxy_route_hard_blacklisted_returns_none(self, state):
        async def run():
            addr = "1.2.3.4:8080"
            state.ratings[addr] = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1, checks_ok=1)
            state.blacklist_add(addr, "manual")
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            result = await runner._connect_by_route(f"proxy:{addr}", "example.com", 80)
            assert result is None
        asyncio.run(run())

    def test_proxy_route_ip_blacklisted_allowed(self, state):
        async def run():
            addr = "127.0.0.1:1"
            r = hunt.ProxyRating(address=addr, last_status="ok", checks_total=1, checks_ok=1)
            r.egress_ip = "8.8.8.8"
            state.ratings[addr] = r
            state._parse_ip_blacklist("8.8.8.8\n", "test", "Test Source")
            state._apply_ip_blacklist_to_proxy(addr, r.egress_ip)
            assert r.is_blacklisted is True
            assert r.in_blacklist is False
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            result = await runner._connect_by_route(f"proxy:{addr}", "example.com", 80)
            assert result is None
        asyncio.run(run())

    def test_connect_by_route_direct_returns_chain(self, state):
        async def run():
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            chain = []
            result = await runner._connect_by_route("direct", "127.0.0.1", 9)
            assert result is None
            assert chain == []
            server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
            try:
                port = server.sockets[0].getsockname()[1]
                chain = []
                result = await runner._connect_by_route("direct", "127.0.0.1", port, chain)
                assert result is not None
                assert chain == ["direct"]
                r, w, _ = result
                w.close()
                await w.wait_closed()
            finally:
                server.close()
                await server.wait_closed()
        asyncio.run(run())

    def test_connect_by_route_pool_selected_uses_active_then_pool(self, state):
        async def run():
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            runner.active_proxy_addr = "1.2.3.4:8080"
            calls = []

            async def fake_via_addr(addr, host, port, chain, need_connect):
                calls.append(("addr", addr))
                return ("ar", "aw", False)

            async def fake_via_pool(host, port, chain, need_connect):
                calls.append(("pool",))
                return ("pr", "pw", False)

            runner._connect_via_addr = fake_via_addr
            runner._connect_via_pool = fake_via_pool

            result = await runner._connect_by_route("pool_selected", "example.com", 80, [])
            assert result == ("ar", "aw", False)
            assert calls[0] == ("addr", "1.2.3.4:8080")

            runner.active_proxy_addr = None
            calls.clear()
            result = await runner._connect_by_route("pool_selected", "example.com", 80, [])
            assert result == ("pr", "pw", False)
            assert calls == [("pool",)]
        asyncio.run(run())

    def test_connect_by_route_http_non_connect_returns_raw(self, state):
        async def run():
            async def proxy_handler(reader, writer):
                line = await reader.readline()
                while True:
                    hdr = await reader.readline()
                    if hdr in (b"\r\n", b"\n", b""):
                        break
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\nOK-PROXY")
                await writer.drain()
                writer.close()
                await writer.wait_closed()

            proxy_server = await asyncio.start_server(proxy_handler, "127.0.0.1", 0)
            proxy_port = proxy_server.sockets[0].getsockname()[1]
            proxy_addr = f"127.0.0.1:{proxy_port}"
            r = state.ratings[proxy_addr] = hunt.ProxyRating(
                address=proxy_addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1)
            r.supports_connect = False

            runner = hunt.ProxyRunner(state, "127.0.0.1")
            chain = []
            result = await runner._connect_by_route(
                f"proxy:{proxy_addr}", "example.com", 80, chain, need_connect=False)
            assert result is not None
            up_r, up_w, is_raw = result
            assert is_raw is True
            assert chain == [f"proxy:{proxy_addr}"]

            up_w.write(b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n")
            await up_w.drain()
            data = await asyncio.wait_for(up_r.read(4096), timeout=5)
            assert b"OK-PROXY" in data, data
            up_w.close()
            await up_w.wait_closed()

            proxy_server.close()
            await proxy_server.wait_closed()

        asyncio.run(run())

    def test_http_connect_retries_on_503(self, state, monkeypatch):
        """http_connect retries on transient 503 and succeeds on second attempt."""
        async def run():
            from hunt.conn import http_connect, _HTTP_CONNECT_RETRY_DELAY
            monkeypatch.setattr("hunt.conn._HTTP_CONNECT_RETRY_DELAY", 0.0)
            attempt_count = [0]

            async def proxy_handler(reader, writer):
                for i in range(3):
                    line = await reader.readline()
                    if not line:
                        break
                    while True:
                        hdr = await reader.readline()
                        if hdr in (b"\r\n", b"\n", b""):
                            break
                    if i == 0:
                        writer.write(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
                    else:
                        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    await writer.drain()
                    if i > 0:
                        await asyncio.sleep(5)
                        break
                writer.close()

            server = await asyncio.start_server(proxy_handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                ok = await asyncio.wait_for(http_connect(reader, writer, "example.com", 443), timeout=10)
                assert ok is True
                writer.close()
                await writer.wait_closed()
            finally:
                server.close()
                await server.wait_closed()

        asyncio.run(run())

    def test_http_connect_no_retry_on_403(self, state, monkeypatch):
        """http_connect does not retry on permanent 403."""
        async def run():
            from hunt.conn import http_connect
            monkeypatch.setattr("hunt.conn._HTTP_CONNECT_RETRY_DELAY", 0.0)
            attempt_count = [0]

            async def proxy_handler(reader, writer):
                attempt_count[0] += 1
                line = await reader.readline()
                while True:
                    hdr = await reader.readline()
                    if hdr in (b"\r\n", b"\n", b""):
                        break
                writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                await asyncio.sleep(5)
                writer.close()

            server = await asyncio.start_server(proxy_handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                ok = await asyncio.wait_for(http_connect(reader, writer, "example.com", 443), timeout=10)
                assert ok is False
                assert attempt_count[0] == 1
                writer.close()
                await writer.wait_closed()
            finally:
                server.close()
                await server.wait_closed()

        asyncio.run(run())

    def test_connect_via_rating_retries_on_failure(self, state, monkeypatch):
        """_connect_via_rating retries: first attempt fails, second succeeds."""
        async def run():
            monkeypatch.setattr(proxy_routing, "_RETRY_DELAYS", (0.0, 0.0, 0.0))
            attempt_count = [0]

            async def proxy_handler(reader, writer):
                attempt_count[0] += 1
                if attempt_count[0] == 1:
                    writer.close()
                    return
                line = await reader.readline()
                while True:
                    hdr = await reader.readline()
                    if hdr in (b"\r\n", b"\n", b""):
                        break
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                await asyncio.sleep(5)
                writer.close()

            server = await asyncio.start_server(proxy_handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            addr = f"127.0.0.1:{port}"
            state.ratings[addr] = hunt.ProxyRating(
                address=addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1, supports_connect=True)

            runner = hunt.ProxyRunner(state, "127.0.0.1")
            chain = []
            result = await runner._connect_by_route(f"proxy:{addr}", "example.com", 443, chain)
            assert result is not None
            assert attempt_count[0] == 2
            assert "retry:1" in chain[0]

            up_r, up_w, _ = result
            up_w.close()
            await up_w.wait_closed()
            server.close()
            await server.wait_closed()

        asyncio.run(run())

    def test_proxy_route_falls_back_to_pool(self, state, monkeypatch):
        """Selected proxy fails after retries → falls back to pool."""
        async def run():
            monkeypatch.setattr(proxy_routing, "_RETRY_DELAYS", (0.0, 0.0, 0.0))

            async def good_proxy_handler(reader, writer):
                line = await reader.readline()
                while True:
                    hdr = await reader.readline()
                    if hdr in (b"\r\n", b"\n", b""):
                        break
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                await asyncio.sleep(5)
                writer.close()

            good_server = await asyncio.start_server(good_proxy_handler, "127.0.0.1", 0)
            good_port = good_server.sockets[0].getsockname()[1]
            good_addr = f"127.0.0.1:{good_port}"

            bad_addr = "127.0.0.1:1"
            state.ratings[bad_addr] = hunt.ProxyRating(
                address=bad_addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1, supports_connect=True)
            state.ratings[good_addr] = hunt.ProxyRating(
                address=good_addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1, supports_connect=True)

            runner = hunt.ProxyRunner(state, "127.0.0.1")
            chain = []
            result = await runner._connect_by_route(f"proxy:{bad_addr}", "example.com", 443, chain)
            assert result is not None
            assert any("fallback" in c for c in chain)
            assert any("pool:" in c for c in chain)
            assert state.ratings[bad_addr].consecutive_fails == 1
            assert state.ratings[bad_addr].last_status == "failed"

            up_r, up_w, _ = result
            up_w.close()
            await up_w.wait_closed()
            good_server.close()
            await good_server.wait_closed()

        asyncio.run(run())

    def test_connect_fallback_active_proxy_to_pool(self, state, monkeypatch):
        """_connect_fallback: active_proxy fails → pool fallback."""
        async def run():
            monkeypatch.setattr(proxy_routing, "_RETRY_DELAYS", (0.0, 0.0, 0.0))

            async def good_proxy_handler(reader, writer):
                line = await reader.readline()
                while True:
                    hdr = await reader.readline()
                    if hdr in (b"\r\n", b"\n", b""):
                        break
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                await asyncio.sleep(5)
                writer.close()

            good_server = await asyncio.start_server(good_proxy_handler, "127.0.0.1", 0)
            good_port = good_server.sockets[0].getsockname()[1]
            good_addr = f"127.0.0.1:{good_port}"

            bad_addr = "127.0.0.1:1"
            state.ratings[bad_addr] = hunt.ProxyRating(
                address=bad_addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1, supports_connect=True)
            state.ratings[good_addr] = hunt.ProxyRating(
                address=good_addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1, supports_connect=True)

            runner = hunt.ProxyRunner(state, "127.0.0.1")
            runner.active_proxy_addr = bad_addr
            chain = []
            result = await runner._connect_fallback("example.com", 443, chain, need_connect=True)
            assert result is not None
            assert any("fallback" in c for c in chain)
            assert any("pool:" in c for c in chain)
            assert state.ratings[bad_addr].consecutive_fails == 1
            assert state.ratings[bad_addr].last_status == "failed"

            up_r, up_w, _ = result
            up_w.close()
            await up_w.wait_closed()
            good_server.close()
            await good_server.wait_closed()

        asyncio.run(run())


class TestUnstableProxyConnect:
    """Fail-fast retry policy: retry when the PROXY is dead, never retry a
    refusal (proxy alive but target unreachable)."""

    def test_refusal_not_retried(self, state, monkeypatch):
        """Proxy answers but refuses CONNECT → single connection, no retries."""
        async def run():
            monkeypatch.setattr(proxy_routing, "_RETRY_DELAYS", (0.0, 0.0, 0.0))
            peers = set()

            async def proxy_handler(reader, writer):
                peers.add(writer.get_extra_info("peername"))
                try:
                    while True:
                        await reader.readline()
                        while True:
                            hdr = await reader.readline()
                            if hdr in (b"\r\n", b"\n", b""):
                                break
                        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                        await writer.drain()
                except Exception:
                    pass
                writer.close()

            server = await asyncio.start_server(proxy_handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            addr = f"127.0.0.1:{port}"
            state.ratings[addr] = hunt.ProxyRating(
                address=addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1, supports_connect=True)

            runner = hunt.ProxyRunner(state, "127.0.0.1")
            result = await runner._connect_by_route(f"proxy:{addr}", "example.com", 443, [])
            assert result is None
            assert len(peers) == 1, "refusal must not open a new connection"
            server.close()
            await server.wait_closed()

        asyncio.run(run())

    def test_tcp_down_retried_with_backoff(self, state, monkeypatch):
        """Proxy TCP unreachable → retried (up to _CONNECT_RETRIES)."""
        async def run():
            monkeypatch.setattr(proxy_routing, "_RETRY_DELAYS", (0.0, 0.0, 0.0))
            addr = "127.0.0.1:1"
            state.ratings[addr] = hunt.ProxyRating(
                address=addr, protocol="http", last_status="ok",
                checks_total=1, checks_ok=1, supports_connect=True)
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            t0 = asyncio.get_event_loop().time()
            result = await runner._connect_by_route(f"proxy:{addr}", "example.com", 443, [])
            assert result is None
            assert state.ratings[addr].consecutive_fails == 1

        asyncio.run(run())


class FakeWriter:
    def __init__(self):
        self.written = b""
        self.closed = False

    def write(self, data):
        self.written += data

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


class FakeUpstream:
    """Reader that returns queued response heads, then dies."""

    def __init__(self, heads):
        self.heads = list(heads)
        self.writer = FakeWriter()

    async def readuntil(self, sep):
        if not self.heads:
            raise ConnectionError("upstream died")
        return self.heads.pop(0)


class TestHttpForwardRetry:
    """Retry of headless HTTP forward when upstream dies before the response
    head completed (client has seen nothing yet)."""

    def test_retry_before_first_byte(self, state):
        async def run():
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            connects = [0]

            async def fake_upstream(host, port, need_connect=True):
                connects[0] += 1
                if connects[0] == 1:
                    return FakeUpstream([]), FakeWriter(), ["proxy:bad"], False
                return (FakeUpstream([b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n"]),
                        FakeWriter(), ["proxy:good"], False)

            runner._connect_upstream = fake_upstream

            got = {}

            async def client_handler(reader, writer):
                peer = writer.get_extra_info("peername")
                await runner._handle_http_forward(
                    reader, writer, b"GET", b"http://example.com/", peer, time.time())
                writer.close()

            server = await asyncio.start_server(client_handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n")
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(), timeout=5)
            writer.close()
            await writer.wait_closed()

            assert b"HTTP/1.1 200 OK" in resp, resp
            assert connects[0] == 2
            assert any(e["status"] == "ok (retry:1)" for e in runner.log)
            server.close()
            await server.wait_closed()

        asyncio.run(run())

    def test_no_retry_when_request_has_body(self, state):
        async def run():
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            connects = [0]

            async def fake_upstream(host, port, need_connect=True):
                connects[0] += 1
                return FakeUpstream([]), FakeWriter(), ["proxy:bad"], False

            runner._connect_upstream = fake_upstream

            async def client_handler(reader, writer):
                peer = writer.get_extra_info("peername")
                await runner._handle_http_forward(
                    reader, writer, b"POST", b"http://example.com/", peer, time.time())
                writer.close()

            server = await asyncio.start_server(client_handler, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"POST / HTTP/1.1\r\nHost: example.com\r\nContent-Length: 5\r\n\r\nhello")
            await writer.drain()
            resp = await asyncio.wait_for(reader.read(), timeout=5)
            writer.close()
            await writer.wait_closed()

            assert b"502" in resp
            assert connects[0] == 1, "body requests must not be replayed"
            server.close()
            await server.wait_closed()

        asyncio.run(run())

    def test_request_has_body_detection(self, state):
        runner = hunt.ProxyRunner(state, "127.0.0.1")
        assert runner._request_has_body([b"Host: x\r\n"]) is False
        assert runner._request_has_body([b"Content-Length: 0\r\n"]) is False
        assert runner._request_has_body([b"Content-Length: 5\r\n"]) is True
        assert runner._request_has_body([b"Transfer-Encoding: chunked\r\n"]) is True
