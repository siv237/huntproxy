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


def mock_resolve_geo(state, cc, country, hosting=False, proxy=False):
    """Patch _resolve_geo so the direct egress lookup matches the fixture."""
    async def fake(ip):
        return {"country": country, "country_code": cc, "city": "X",
                "isp": "Y", "hosting": hosting, "proxy": proxy, "mobile": False}
    state._resolve_geo = fake


EGRESS_JSON = b'{"query":"1.2.3.4","country":"Germany","countryCode":"DE","city":"Berlin","isp":"Test ISP"}'


class FakeSocksProxyServer:
    """Local SOCKS server speaking both SOCKS5 and SOCKS4 (sniffed from the
    first byte), accepts any target and answers in-tunnel ip-api GET requests
    with a fixed JSON payload."""

    def __init__(self, deny: bool = False):
        self.deny = deny
        self.host = "127.0.0.1"
        self.port = 0
        self.server = None
        self.targets = []
        self.requests = []

    async def start(self):
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _serve_get(self, reader, writer):
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            self.requests.append(head)
            if head.startswith(b"GET "):
                writer.write(
                    b"HTTP/1.0 200 OK\r\nContent-Length: "
                    + str(len(EGRESS_JSON)).encode()
                    + b"\r\nConnection: close\r\n\r\n" + EGRESS_JSON)
                await writer.drain()
        except Exception:
            pass

    async def _handle(self, reader, writer):
        try:
            first = await reader.readexactly(1)
            if first == b"\x05":
                ok = await self._socks5_handshake(reader, writer)
            elif first == b"\x04":
                ok = await self._socks4_handshake(reader, writer)
            else:
                return
            if ok:
                await self._serve_get(reader, writer)
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _socks5_handshake(self, reader, writer) -> bool:
        nmethods = (await reader.readexactly(1))[0]
        await reader.readexactly(nmethods)
        if self.deny:
            writer.write(bytes([5, 0xFF]))
            await writer.drain()
            return False
        writer.write(bytes([5, 0]))
        await writer.drain()
        req = await reader.readexactly(4)
        if req[0] != 5 or req[1] != 1:
            return False
        if req[3] == 1:
            raw = await reader.readexactly(4)
            host = ".".join(str(b) for b in raw)
        elif req[3] == 3:
            host = (await reader.readexactly((await reader.readexactly(1))[0])).decode()
        elif req[3] == 4:
            await reader.readexactly(16)
            host = ""
        else:
            return False
        port = int.from_bytes(await reader.readexactly(2), "big")
        self.targets.append((host, port))
        writer.write(bytes([5, 0, 0, 1, 127, 0, 0, 1, 0, 0]))
        await writer.drain()
        return True

    async def _socks4_handshake(self, reader, writer) -> bool:
        # request: [4][CMD][DSTPORT:2][DSTIP:4][USERID\0][HOST\0] — first byte consumed
        hdr = await reader.readexactly(7)
        if hdr[0] != 1:
            return False
        host = b""
        while True:
            b = await reader.readexactly(1)
            if b == b"\x00":
                break
            host += b
        if int.from_bytes(hdr[3:7], "big") == 1:
            host = b""
            while True:
                b = await reader.readexactly(1)
                if b == b"\x00":
                    break
                host += b
        self.targets.append((host.decode(), int.from_bytes(hdr[1:3], "big")))
        reply = bytes([0, 0x5B if self.deny else 0x5A]) + hdr[1:]
        writer.write(reply)
        await writer.drain()
        return not self.deny


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
                mock_resolve_geo(state, "US", "United States")
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
                mock_resolve_geo(state, "DE", "Germany")
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
                mock_resolve_geo(state, "US", "United States")
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
                mock_resolve_geo(state, "US", "United States")
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is False
                assert supports_connect is False
                assert latency > 0
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_proxy_http_spoofed_egress_rejected(self, state):
        """A proxy that claims an egress country contradicting its real IP
        (geo-spoofing) must be rejected before reaching the rating."""
        resp = b'{"query":"1.2.3.4","country":"United Kingdom","countryCode":"GB","city":"London","isp":"Fake ISP"}'
        proxy = FakeHttpProxyServer(resp)

        async def run():
            await proxy.start()
            try:
                async def fake_connect(host, port, is_socks):
                    return True, False
                state._check_proxy_connect = fake_connect
                # Direct lookup says this egress IP is really in Australia.
                mock_resolve_geo(state, "AU", "Australia", hosting=True, proxy=True)
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is False
                assert latency == 0.0
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_proxy_http_consistent_egress_uses_authoritative_geo(self, state):
        """When the proxy's egress is genuine, the authoritative direct lookup
        (hosting/proxy flags) must override the proxy's self-reported flags."""
        resp = b'{"query":"1.2.3.4","country":"United States","countryCode":"US","hosting":false,"proxy":false}'
        proxy = FakeHttpProxyServer(resp)

        async def run():
            await proxy.start()
            try:
                async def fake_connect(host, port, is_socks):
                    return True, False
                state._check_proxy_connect = fake_connect
                # Real egress IS a datacenter/proxy even though the proxy lied.
                mock_resolve_geo(state, "US", "United States", hosting=True, proxy=True)
                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is True
                assert egress["egress_hosting"] is True
                assert egress["egress_proxy"] is True
                assert egress["egress_country"] == "United States"
                assert country_code == "US"
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_proxy_http_egress_lookup_uncertain_keeps_reported(self, state):
        """Fail-open: if the direct egress lookup returns nothing (transient
        ip-api outage), a genuine proxy must not be evicted."""
        resp = b'{"query":"1.2.3.4","country":"United States","countryCode":"US","hosting":false,"proxy":false}'
        proxy = FakeHttpProxyServer(resp)

        async def run():
            await proxy.start()
            try:
                async def fake_connect(host, port, is_socks):
                    return True, False
                state._check_proxy_connect = fake_connect

                async def fake_geo(ip):
                    return {}
                state._resolve_geo = fake_geo

                ok, country, supports_connect, mitm_suspect, egress, listen, latency, country_code, fast_fail = await state._check_proxy(
                    f"127.0.0.1:{proxy.port}"
                )
                assert ok is True
                assert country == "United States"
                assert country_code == "US"
            finally:
                await proxy.stop()

        asyncio.run(run())


class TestSocksTestMethods:
    """Regression: 8496c53 deleted _socks5_test/_socks4_test along with the
    old curl-based MITM code, but check_proxy/check_speed kept calling them —
    the AttributeError was swallowed by gather(return_exceptions=True) and
    every SOCKS proxy silently failed the check."""

    def test_methods_defined_on_hunt_state(self):
        assert callable(hunt.HuntState._socks5_test)
        assert callable(hunt.HuntState._socks4_test)

    def test_socks5_test_accepts_working_proxy(self, state):
        proxy = FakeSocksProxyServer()

        async def run():
            await proxy.start()
            try:
                r, w = await state._outbound_connect(proxy.host, proxy.port)
                try:
                    assert await state._socks5_test(r, w) is True
                finally:
                    w.close()
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_socks5_test_rejects_refusal(self, state):
        proxy = FakeSocksProxyServer(deny=True)

        async def run():
            await proxy.start()
            try:
                r, w = await state._outbound_connect(proxy.host, proxy.port)
                try:
                    assert await state._socks5_test(r, w) is False
                finally:
                    w.close()
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_socks4_test_accepts_working_proxy(self, state):
        proxy = FakeSocksProxyServer()

        async def run():
            await proxy.start()
            try:
                r, w = await state._outbound_connect(proxy.host, proxy.port)
                try:
                    assert await state._socks4_test(r, w) is True
                finally:
                    w.close()
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_socks4_test_rejects_refusal(self, state):
        proxy = FakeSocksProxyServer(deny=True)

        async def run():
            await proxy.start()
            try:
                r, w = await state._outbound_connect(proxy.host, proxy.port)
                try:
                    assert await state._socks4_test(r, w) is False
                finally:
                    w.close()
            finally:
                await proxy.stop()

        asyncio.run(run())


class TestCheckSocksProxyPipeline:
    def test_check_socks_proxy_socks5_ok(self, state):
        proxy = FakeSocksProxyServer()

        async def run():
            await proxy.start()
            try:
                mock_resolve_geo(state, "DE", "Germany")
                listen_task = asyncio.create_task(state._resolve_geo("127.0.0.1"))
                r, w = await state._outbound_connect(proxy.host, proxy.port)
                result = await state._check_socks_proxy(
                    r, w, proxy.host, proxy.port, 0.0, listen_task)
                ok, country, supports_connect, mitm, egress, listen, latency, cc = result
                assert ok is True
                assert egress.get("egress_ip") == "1.2.3.4"
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_socks_proxy_socks4(self, state):
        """Port 4145 selects the SOCKS4 branch; remap outbound connections so
        the in-tunnel egress probe reaches the same fake (no real 4145 here)."""
        proxy = FakeSocksProxyServer()
        orig = state._outbound_connect

        async def run():
            await proxy.start()
            try:
                mock_resolve_geo(state, "DE", "Germany")

                async def fake_outbound(host, port, **kw):
                    return await orig(proxy.host, proxy.port, **kw)
                state._outbound_connect = fake_outbound
                listen_task = asyncio.create_task(state._resolve_geo("127.0.0.1"))
                r, w = await orig(proxy.host, proxy.port)
                result = await state._check_socks_proxy(
                    r, w, proxy.host, 4145, 0.0, listen_task)
                ok, country, supports_connect, mitm, egress, listen, latency, cc = result
                assert ok is True
                assert egress.get("egress_ip") == "1.2.3.4"
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_check_socks_proxy_refused(self, state):
        proxy = FakeSocksProxyServer(deny=True)

        async def run():
            await proxy.start()
            try:
                async def fake_geo(ip):
                    return {}
                state._resolve_geo = fake_geo
                listen_task = asyncio.create_task(state._resolve_geo("127.0.0.1"))
                r, w = await state._outbound_connect(proxy.host, proxy.port)
                result = await state._check_socks_proxy(
                    r, w, "127.0.0.1", 1080, 0.0, listen_task)
                ok = result[0]
                assert ok is False
            finally:
                await proxy.stop()

        asyncio.run(run())


class TestSpeedOverSocks:
    def test_speed_open_socks5_establishes_tunnel(self, state):
        proxy = FakeSocksProxyServer()

        async def run():
            await proxy.start()
            try:
                conn = await state._speed_open(proxy.host, proxy.port, True, False)
                assert conn is not None
                r, w = conn
                w.close()
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_speed_single_socks5_measures(self, state):
        proxy = FakeSocksProxyServer()

        async def run():
            await proxy.start()
            try:
                speed = await state._speed_single(
                    proxy.host, proxy.port, is_socks=True,
                    srv_host="example.com", srv_path="/file",
                    expected_size=len(EGRESS_JSON), use_ssl=False,
                    supports_connect=False)
                assert speed > 0.0
                assert ("example.com", 80) in proxy.targets
                assert proxy.requests and proxy.requests[-1].startswith(b"GET /file ")
            finally:
                await proxy.stop()

        asyncio.run(run())

    def test_speed_open_socks5_refused_returns_none(self, state):
        proxy = FakeSocksProxyServer(deny=True)

        async def run():
            await proxy.start()
            try:
                conn = await state._speed_open(proxy.host, proxy.port, True, False)
                assert conn is None
            finally:
                await proxy.stop()

        asyncio.run(run())
