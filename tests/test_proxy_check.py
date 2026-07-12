import asyncio
import pytest
import hunt


class FakeHttpProxyServer:
    """Local HTTP proxy that returns a fake ip-api.com response."""

    def __init__(self, ip_api_response: bytes, country_code: str = "US"):
        self.ip_api_response = ip_api_response
        self.host = "127.0.0.1"
        self.port = 0
        self.server = None
        self.requests = []

    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle(self, reader, writer):
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            self.requests.append(head)
            req = head.decode(errors="replace").split("\r\n")[0]
            if req.startswith("GET http://ip-api.com/json/"):
                response = (
                    b"HTTP/1.0 200 OK\r\n"
                    b"Content-Length: " + str(len(self.ip_api_response)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n"
                    + self.ip_api_response
                )
                writer.write(response)
                await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class TestCheckProxyHttp:
    def test_check_proxy_http_ok(self, state):
        resp = b'{"query":"1.2.3.4","country":"United States","countryCode":"US","city":"New York","isp":"Test ISP"}'
        proxy = FakeHttpProxyServer(resp)

        async def run():
            await proxy.start()
            try:
                async def fake_connect(host, port, is_socks):
                    return True, False
                state._check_proxy_connect = fake_connect
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is True
                assert country == "United States"
                assert country_code == "US"
                assert egress.get("egress_ip") == "1.2.3.4"
                assert supports_connect is True
                assert mitm_suspect is False
                assert latency > 0
                assert fast_fail is False
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_proxy_http_non_us_filtered(self, state):
        resp = b'{"query":"5.6.7.8","country":"Germany","countryCode":"DE","city":"Berlin","isp":"Test ISP"}'
        proxy = FakeHttpProxyServer(resp)

        async def run():
            await proxy.start()
            try:
                async def fake_connect(host, port, is_socks):
                    return True, False
                state._check_proxy_connect = fake_connect
                state.us_only = True
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is False
                assert country_code == "DE"
                assert latency == 0.0
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_proxy_http_country_filter(self, state):
        resp = b'{"query":"1.2.3.4","country":"United States","countryCode":"US","city":"New York","isp":"Test ISP"}'
        proxy = FakeHttpProxyServer(resp)

        async def run():
            await proxy.start()
            try:
                async def fake_connect(host, port, is_socks):
                    return True, False
                state._check_proxy_connect = fake_connect
                state.country_filter = "GB"
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is False
                assert country_code == "US"
                assert latency == 0.0
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_proxy_http_bad_ip_api_response(self, state):
        proxy = FakeHttpProxyServer(b"not json")

        async def run():
            await proxy.start()
            try:
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is False
                assert latency == 0.0
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_proxy_http_refused_port(self, state):
        async def run():
            ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                "127.0.0.1:1"
            )
            assert ok is False
            assert latency == 0.0

        asyncio.run(run())

    def test_auto_pause_clears_pause_event_synchronously(self, state):
        """Regression: when internet is suspected, _pause_event must be cleared
        synchronously so every _check_one waiter actually suspends instead of
        busy-looping on an already-set event (which starved the event loop and
        hung the whole service)."""

        async def run():
            canary_started = asyncio.Event()
            canary_release = asyncio.Event()

            async def fake_canary():
                canary_started.set()
                await canary_release.wait()
                return True

            state.is_internet_alive = fake_canary
            state._fail_streak = 20
            state._check_streak = 20

            task = asyncio.create_task(state._auto_pause_if_internet_down())
            await asyncio.wait_for(canary_started.wait(), 2)

            assert state._internet_suspect is True
            assert not state._pause_event.is_set(), (
                "pause_event must be cleared while internet is suspected, "
                "otherwise checkers busy-loop and starve the event loop"
            )

            canary_release.set()
            await asyncio.wait_for(task, 2)
            assert state._internet_suspect is False
            assert state._pause_event.is_set()

        asyncio.run(run())

    def test_internet_suspect_does_not_starve_event_loop(self, state):
        """Regression: the check_one wait pattern must suspend (not spin) when
        internet is suspected, so the event loop and the canary keep running."""

        async def run():
            beats = 0

            async def heartbeat():
                nonlocal beats
                for _ in range(20):
                    beats += 1
                    await asyncio.sleep(0.01)

            async def checker_loop():
                # mirrors the busy-loop-prone pattern in check_validation._check_one
                while True:
                    if state._internet_suspect:
                        await state._pause_event.wait()
                        continue
                    break

            state._internet_suspect = True
            state._pause_event.clear()  # correct precondition (set by the fix)

            hb = asyncio.create_task(heartbeat())
            cw = asyncio.create_task(checker_loop())
            await asyncio.sleep(0.2)  # if buggy, the loop would spin here

            state._internet_suspect = False
            state._pause_event.set()
            await asyncio.wait_for(cw, timeout=2)
            await hb
            assert beats >= 10, "event loop was starved by the checker busy-loop"

        asyncio.run(run())

    def test_check_proxy_http_no_connect_is_failed(self, state):
        resp = b'{"query":"1.2.3.4","country":"United States","countryCode":"US","city":"New York","isp":"Test ISP"}'
        proxy = FakeHttpProxyServer(resp)

        async def run():
            await proxy.start()
            try:
                async def fake_connect(host, port, is_socks):
                    return False, False
                state._check_proxy_connect = fake_connect
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is False
                assert supports_connect is False
                assert latency > 0
            finally:
                await proxy.stop()

        asyncio.run(run())
