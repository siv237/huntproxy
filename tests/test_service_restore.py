import asyncio
import json
import hunt


class TestServiceStatePersistence:
    def test_save_and_load_service_state(self, state, tmp_data_dir):
        state._hunt_running = True
        state._proxy_running = True
        state._proxy_port = 17333
        state._socks5_running = True
        state._socks5_port = 17444
        state._proxy_direct_mode = True
        state._proxy_active_addr = "1.2.3.4:8080"
        state._save_state()

        state2 = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        assert state2._hunt_running is True
        assert state2._proxy_running is True
        assert state2._proxy_port == 17333
        assert state2._socks5_running is True
        assert state2._socks5_port == 17444
        assert state2._proxy_direct_mode is True
        assert state2._proxy_active_addr == "1.2.3.4:8080"

    def test_service_state_defaults_when_missing(self, state, tmp_data_dir):
        state._save_state()
        state2 = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        assert state2._hunt_running is False
        assert state2._proxy_running is False
        assert state2._proxy_port == 17277
        assert state2._socks5_running is False
        assert state2._socks5_port == 17278
        assert state2._proxy_direct_mode is False
        assert state2._proxy_active_addr is None

    def test_start_hunt_sets_running_flag(self, state):
        async def run():
            assert state._hunt_running is False
            result = state.start_hunt()
            assert result is True
            assert state._hunt_running is True
            state.stop_hunt()
            assert state._hunt_running is False
        asyncio.run(run())

    def test_proxy_runner_start_sets_state(self):
        async def run():
            state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
            runner = hunt.ProxyRunner(state, "127.0.0.1")
            await runner.start(17333)
            assert state._proxy_running is True
            assert state._proxy_port == 17333
            await runner.stop()
            assert state._proxy_running is False

        asyncio.run(run())

    def test_socks5_runner_start_sets_state(self):
        async def run():
            state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
            runner = hunt.Socks5Runner(state, "127.0.0.1")
            await runner.start(17444)
            assert state._socks5_running is True
            assert state._socks5_port == 17444
            await runner.stop()
            assert state._socks5_running is False

        asyncio.run(run())

    def test_stop_hunt_clears_running_flag(self, state):
        async def run():
            state.start_hunt()
            assert state._hunt_running is True
            state.stop_hunt()
            assert state._hunt_running is False
        asyncio.run(run())

    def test_proxy_select_saves_active_addr(self, state):
        runner = hunt.ProxyRunner(state, "127.0.0.1")
        runner.select("1.2.3.4:8080")
        state._proxy_active_addr = runner.active_proxy_addr
        state._save_state()
        state2 = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        assert state2._proxy_active_addr == "1.2.3.4:8080"

    def test_hunt_server_restores_service_state(self, tmp_data_dir):
        async def run():
            state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
            state._hunt_running = True
            state._proxy_running = True
            state._proxy_port = 17333
            state._socks5_running = True
            state._socks5_port = 17444
            state._proxy_active_addr = "1.2.3.4:8080"

            server = hunt.HuntServer(state, "127.0.0.1", 0)
            state.proxy_runner = server.proxy

            # Restore services (same logic as in amain)
            restored = []
            if getattr(state, '_hunt_running', False):
                if state.start_hunt():
                    restored.append("hunt")
            if getattr(state, '_proxy_running', False):
                proxy_port = getattr(state, '_proxy_port', 17277)
                await server.proxy.start(proxy_port)
                restored.append(f"proxy:{proxy_port}")
            if getattr(state, '_socks5_running', False):
                socks5_port = getattr(state, '_socks5_port', 17278)
                await server.socks5.start(socks5_port)
                restored.append(f"socks5:{socks5_port}")
            if getattr(state, '_proxy_active_addr', None):
                server.proxy.select(state._proxy_active_addr)

            assert "hunt" in restored
            assert "proxy:17333" in restored
            assert "socks5:17444" in restored
            assert server.proxy.running is True
            assert server.socks5.running is True
            assert server.proxy.active_proxy_addr == "1.2.3.4:8080"

            await server.proxy.stop()
            await server.socks5.stop()
            state.stop_hunt()

        asyncio.run(run())
