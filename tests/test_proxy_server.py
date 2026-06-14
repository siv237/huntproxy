import asyncio
import pytest
import hunt


class TestProxyServer:
    def test_proxy_runner_start_stop(self):
        async def run():
            state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            await runner.start(0)
            assert runner.running is True
            # Wait for _run to create the server
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

    def test_socks5_runner_start_stop(self):
        async def run():
            state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
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

    def test_proxy_runner_select_sets_active_address(self):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        runner = hunt.ProxyRunner(state, "127.0.0.1")
        runner.select("1.2.3.4:8080")
        assert runner.active_proxy_addr == "1.2.3.4:8080"
        # select creates a rating if missing
        assert runner.selected_proxy is not None
        assert runner.selected_proxy.address == "1.2.3.4:8080"

    def test_proxy_runner_direct_mode(self):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        runner = hunt.ProxyRunner(state, "127.0.0.1")
        assert runner.direct_mode is False
        runner.direct_mode = True
        assert runner.direct_mode is True

    def test_socks5_runner_selected_proxy_uses_state_runner(self):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state.proxy_runner = hunt.ProxyRunner(state, "127.0.0.1")
        state.proxy_runner.select("1.2.3.4:1080")
        runner = hunt.Socks5Runner(state, "127.0.0.1")
        assert runner.selected_proxy is not None
        assert runner.selected_proxy.address == "1.2.3.4:1080"
