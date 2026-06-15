import pytest
import tempfile
import asyncio
from pathlib import Path
import sys
import importlib
import hunt
import hunt.constants
import hunt.state
import hunt.server


@pytest.fixture
def tmp_data_dir(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # DATA_DIR is re-bound in several modules by the split; patch all of them.
        _main_module = importlib.import_module("hunt.main")
        for module in (hunt, hunt.constants, hunt.state, hunt.server, _main_module):
            monkeypatch.setattr(module, "DATA_DIR", tmp_path)
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
    """Start a real HuntServer on a random port in a background thread."""
    import threading

    state = hunt.HuntState(empty_config)
    server = hunt.HuntServer(state, "127.0.0.1", 0)
    ready_event = threading.Event()

    async def run():
        server._server = await asyncio.start_server(server._handle, "127.0.0.1", 0)
        addr = server._server.sockets[0].getsockname()
        server.port = addr[1]
        ready_event.set()
        async with server._server:
            await server._server.serve_forever()

    def thread_main():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run())
        except asyncio.CancelledError:
            pass
        finally:
            loop.close()

    thread = threading.Thread(target=thread_main, daemon=True)
    thread.start()
    ready_event.wait(timeout=10)
    if not ready_event.is_set():
        raise RuntimeError("API server failed to start")

    base_url = f"http://127.0.0.1:{server.port}"
    yield base_url, state

    async def stop():
        if server._server:
            server._server.close()
            await server._server.wait_closed()

    if server._server:
        loop = server._server.get_loop()
        asyncio.run_coroutine_threadsafe(stop(), loop)
    thread.join(timeout=5)



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
