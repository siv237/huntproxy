import asyncio
import pytest
import hunt


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
