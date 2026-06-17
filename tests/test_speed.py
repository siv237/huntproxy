import asyncio
import json
import os
import pytest
import shutil
import subprocess
import tempfile
import hunt


class LocalSpeedServer:
    def __init__(self, response_body: bytes):
        self.response_body = response_body
        self.host = "127.0.0.1"
        self.port = 0
        self.server = None

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
            req = head.decode(errors="ignore").split("\r\n")[0]
            if req.startswith("GET "):
                response = (
                    b"HTTP/1.0 200 OK\r\n"
                    b"Content-Length: " + str(len(self.response_body)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n"
                    + self.response_body
                )
                writer.write(response)
                await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            await writer.wait_closed()


class LocalHttpsSpeedServer(LocalSpeedServer):
    def __init__(self, response_body: bytes, cert_path: str, key_path: str):
        super().__init__(response_body)
        self.cert_path = cert_path
        self.key_path = key_path

    async def start(self):
        import ssl as _ssl
        ctx = _ssl.create_default_context(_ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(self.cert_path, self.key_path)
        self.server = await asyncio.start_server(self._handle, self.host, self.port, ssl=ctx)
        self.port = self.server.sockets[0].getsockname()[1]


def _generate_self_signed_cert(tmpdir):
    cert = os.path.join(tmpdir, "server.crt")
    key = os.path.join(tmpdir, "server.key")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key, "-out", cert,
            "-days", "1", "-nodes",
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=IP:127.0.0.1",
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=tmpdir,
    )
    return cert, key


class TestSpeedMeasurement:
    def test_speed_single_direct(self):
        body = b"x" * 102400
        server = LocalSpeedServer(body)

        async def run():
            await server.start()
            try:
                state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
                speed = await state._speed_single(
                    server.host,
                    server.port,
                    is_socks=False,
                    srv_host="example.com",
                    srv_path="/file",
                    expected_size=len(body),
                    use_ssl=False,
                    supports_connect=False,
                )
                assert speed > 0.0
            finally:
                await server.stop()

        asyncio.run(run())

    def test_measure_speed_returns_first_positive(self):
        state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
        state.SPEED_SERVERS = [
            ("example.com", "/file1", 1024),
            ("example.com", "/file2", 1024),
        ]
        call_count = 0

        async def fake_speed_single(host, port, is_socks, srv_host, srv_path, expected_size, use_ssl, supports_connect):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 0.0
            return 100.0

        state._speed_single = fake_speed_single

        async def run():
            speed = await state._measure_speed("127.0.0.1", 8080, False, False)
            assert speed == 100.0
            assert call_count == 2

        asyncio.run(run())

    def test_speed_single_returns_zero_for_non_200(self):
        server = LocalSpeedServer(b"")

        async def run():
            await server.start()
            try:
                state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
                speed = await state._speed_single(
                    server.host,
                    server.port,
                    is_socks=False,
                    srv_host="example.com",
                    srv_path="/missing",
                    expected_size=1024,
                    use_ssl=False,
                    supports_connect=False,
                )
                assert speed == 0.0
            finally:
                await server.stop()

        asyncio.run(run())

    def test_speed_single_https_direct(self):
        tmpdir = tempfile.mkdtemp()
        try:
            cert, key = _generate_self_signed_cert(tmpdir)
            body = b"x" * 102400
            server = LocalHttpsSpeedServer(body, cert, key)

            async def run():
                await server.start()
                try:
                    state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
                    speed = await state._speed_single(
                        server.host,
                        server.port,
                        is_socks=False,
                        srv_host="example.com",
                        srv_path="/file",
                        expected_size=len(body),
                        use_ssl=True,
                        supports_connect=False,
                    )
                    assert speed > 0.0
                finally:
                    await server.stop()

            asyncio.run(run())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_speed_single_https_with_connect_fallback(self):
        tmpdir = tempfile.mkdtemp()
        try:
            cert, key = _generate_self_signed_cert(tmpdir)
            body = b"x" * 102400
            server = LocalHttpsSpeedServer(body, cert, key)

            async def run():
                await server.start()
                try:
                    state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
                    speed = await state._speed_single(
                        server.host,
                        server.port,
                        is_socks=False,
                        srv_host="example.com",
                        srv_path="/file",
                        expected_size=len(body),
                        use_ssl=True,
                        supports_connect=True,
                    )
                    assert speed > 0.0
                finally:
                    await server.stop()

            asyncio.run(run())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class LocalHttpsProxyServer:
    """TLS proxy that requires CONNECT; plain GET is rejected."""

    def __init__(self, cert_path: str, key_path: str):
        self.cert_path = cert_path
        self.key_path = key_path
        self.host = "127.0.0.1"
        self.port = 0
        self.target_host = None
        self.target_port = None
        self.server = None

    async def start(self):
        import ssl as _ssl
        ctx = _ssl.create_default_context(_ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(self.cert_path, self.key_path)
        self.server = await asyncio.start_server(self._handle, self.host, self.port, ssl=ctx)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle(self, client_reader, client_writer):
        try:
            head = await client_reader.readuntil(b"\r\n\r\n")
            req = head.decode(errors="ignore").split("\r\n")[0]
            if req.startswith("GET ") or req.startswith("POST "):
                client_writer.write(b"HTTP/1.1 501 Not Implemented\r\nConnection: close\r\n\r\n")
                await client_writer.drain()
                return
            if not req.startswith("CONNECT "):
                return
            client_writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await client_writer.drain()
            target_reader, target_writer = await asyncio.open_connection(self.target_host, self.target_port)

            async def pipe(reader, writer):
                try:
                    while True:
                        data = await reader.read(65536)
                        if not data:
                            break
                        writer.write(data)
                        await writer.drain()
                except Exception:
                    pass

            await asyncio.gather(
                pipe(client_reader, target_writer),
                pipe(target_reader, client_writer),
                return_exceptions=True,
            )
            target_writer.close()
            try:
                await target_writer.wait_closed()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            client_writer.close()
            await client_writer.wait_closed()


class TestHttpsProxyConnect:
    def test_speed_single_ssl_proxy_requires_connect(self):
        tmpdir = tempfile.mkdtemp()
        try:
            cert, key = _generate_self_signed_cert(tmpdir)
            body = b"x" * 102400
            target = LocalSpeedServer(body)
            proxy = LocalHttpsProxyServer(cert, key)

            async def run():
                await target.start()
                proxy.target_host = target.host
                proxy.target_port = target.port
                await proxy.start()
                try:
                    state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
                    state.SPEED_SERVERS = [("example.com", "/file", len(body))]
                    speed = await state._speed_single(
                        proxy.host,
                        proxy.port,
                        is_socks=False,
                        srv_host="example.com",
                        srv_path="/file",
                        expected_size=len(body),
                        use_ssl=True,
                        supports_connect=True,
                    )
                    assert speed > 0.0
                finally:
                    await proxy.stop()
                    await target.stop()

            asyncio.run(run())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_check_ssl_detects_connect_support(self):
        tmpdir = tempfile.mkdtemp()
        try:
            cert, key = _generate_self_signed_cert(tmpdir)
            json_body = json.dumps({"country": "Testland", "countryCode": "TL", "query": "1.2.3.4", "city": "Test", "isp": "Test"}).encode()
            target = LocalSpeedServer(json_body)
            proxy = LocalHttpsProxyServer(cert, key)

            async def run():
                await target.start()
                proxy.target_host = target.host
                proxy.target_port = target.port
                await proxy.start()
                try:
                    state = hunt.HuntState({"ip_blacklists": {"enabled": False}})
                    ok, country, country_code, egress, latency, supports_connect = await state._check_ssl(f"{proxy.host}:{proxy.port}")
                    assert ok is True
                    assert supports_connect is True
                finally:
                    await proxy.stop()
                    await target.stop()

            asyncio.run(run())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
