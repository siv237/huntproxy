import pytest
import tempfile
import asyncio
from pathlib import Path
import sys
import hunt


@pytest.fixture
def tmp_data_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        monkeypatch.setattr(hunt, "DATA_DIR", tmp_path)
        yield tmp_path


@pytest.fixture
def empty_config():
    return {
        "hunt": {"timeout": 8, "parallel": 30, "health_timeout": 10, "health_parallel": 30},
        "proxies": {"validate_interval": 300, "health_interval": 120, "strategy": "round_robin", "max_failures": 3, "cooldown": 300},
        "ip_blacklists": {"enabled": False, "fetch_interval": 3600},
    }


@pytest.fixture
def state(tmp_data_dir, empty_config):
    return hunt.HuntState(empty_config)


@pytest.fixture
def api_server(tmp_data_dir, empty_config):
    """Start a real HuntServer on a random port and return its base URL."""
    state = hunt.HuntState(empty_config)
    server = hunt.HuntServer(state, "127.0.0.1", 0)
    task = None

    async def run():
        server._server = await asyncio.start_server(server._handle, "127.0.0.1", 0)
        addr = server._server.sockets[0].getsockname()
        server.port = addr[1]
        async with server._server:
            await server._server.serve_forever()

    async def start():
        nonlocal task
        task = asyncio.create_task(run())
        # Wait until the server is actually bound
        for _ in range(50):
            await asyncio.sleep(0.01)
            if getattr(server, "port", 0):
                break
        return f"http://127.0.0.1:{server.port}"

    async def stop():
        if server._server:
            server._server.close()
            await server._server.wait_closed()
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    loop = asyncio.new_event_loop()
    base_url = loop.run_until_complete(start())
    yield base_url, state
    loop.run_until_complete(stop())
    loop.close()


@pytest.fixture
def http_client(api_server):
    base_url, _ = api_server

    async def request(method, path, body=None, headers=None):
        reader, writer = await asyncio.open_connection("127.0.0.1", int(base_url.rsplit(":", 1)[1]))
        try:
            body_bytes = b""
            if body:
                if isinstance(body, str):
                    body_bytes = body.encode()
                elif isinstance(body, dict):
                    body_bytes = hunt.json.dumps(body).encode()
                else:
                    body_bytes = body
            req = f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            if body_bytes:
                req += f"Content-Length: {len(body_bytes)}\r\nContent-Type: application/json\r\n"
            if headers:
                for k, v in headers.items():
                    req += f"{k}: {v}\r\n"
            req += "Connection: close\r\n\r\n"
            writer.write(req.encode())
            if body_bytes:
                writer.write(body_bytes)
            await writer.drain()

            response = b""
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                response += chunk
            return response
        finally:
            writer.close()
            await writer.wait_closed()

    return request
