import asyncio
import pytest
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

        async def fake_speed_single(host, port, is_socks, srv_host, srv_path, expected_size, use_ssl):
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
                )
                assert speed == 0.0
            finally:
                await server.stop()

        asyncio.run(run())
