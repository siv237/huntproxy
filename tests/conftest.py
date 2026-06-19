import pytest
import tempfile
import asyncio
import logging
import time as _time
from datetime import datetime as _dt
from pathlib import Path
import sys
import importlib
import hunt
import hunt.constants
import hunt.state
import hunt.server

# Silence all logging output during tests
logging.disable(logging.CRITICAL)


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


# ── Live grouped test report (os.write = zero flicker) ─────────────────────
import os as _os
from datetime import datetime as _dt

_GROUPS = {
    "actions": "Actions / Snapshots",
    "api": "API",
    "blacklist": "Blacklist",
    "custom_proxies": "Custom Proxies",
    "domain_lists": "Domain Lists / Routing",
    "favorites": "Favorites",
    "health_restore": "Health Restore",
    "ip_blacklist": "IP Blacklist",
    "locales": "Locales",
    "navigation": "Navigation",
    "api_consistency": "API Consistency",
    "proxy_check": "Proxy Checking",
    "proxy_rating": "Proxy Rating / Scoring",
    "proxy_server": "Proxy / SOCKS Server",
    "proxy_sources": "Proxy Sources",
    "service_restore": "Service Restore",
    "speed": "Speed Measurement",
    "ssl_check": "SSL Checking",
    "state_loading": "State Loading / Persistence",
    "traffic": "Traffic Logging",
    "update_rating": "Update Rating",
}


def _gname(path):
    base = path.replace("tests/test_", "").replace(".py", "")
    return _GROUPS.get(base, base)


def _put(s):
    """Write directly to fd 1 (stdout) — bypasses all pytest/capture/buffering."""
    _os.write(1, s.encode())


class _LiveReporter:
    def __init__(self):
        self.groups = {}
        self.order = []
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.failures = []

    def pytest_collection_finish(self, session):
        self.total = len(session.items)
        _put(f"\n  {self.total} tests collected\n\n")

    def pytest_runtest_logreport(self, report):
        if report.when != "call":
            return
        f = report.location[0]
        g = _gname(f)
        if g not in self.groups:
            if self.order:
                e = self.groups[self.order[-1]]
                st = "OK" if e["fail"] == 0 else f"FAIL({e['fail']})"
                _put(f"] {e['ok']}/{e['count']} {st}\n")
            self.groups[g] = {"count": 0, "ok": 0, "fail": 0}
            self.order.append(g)
            ts = _dt.now().strftime("%H:%M:%S")
            _put(f"  {ts}  {g:<24} [")
        e = self.groups[g]
        e["count"] += 1
        if report.passed:
            e["ok"] += 1
            self.passed += 1
            _put(".")
        else:
            e["fail"] += 1
            self.failed += 1
            tb = ""
            try:
                tb = str(report.longreprtext)
            except Exception:
                pass
            self.failures.append((g, report.location[2], tb))
            _put("F")

    def pytest_sessionfinish(self, session, exitstatus):
        if self.order:
            e = self.groups[self.order[-1]]
            st = "OK" if e["fail"] == 0 else f"FAIL({e['fail']})"
            _put(f"] {e['ok']}/{e['count']} {st}\n")
        _put(f"\n  {'='*64}\n")
        _put(f"  Total: {self.passed} passed, {self.failed} failed\n")
        if self.failures:
            _put(f"\n  Failed tests:\n")
            for g, name, _ in self.failures:
                _put(f"    x {g} :: {name}\n")
            _put(f"\n  Tracebacks:\n\n")
            for g, name, tb in self.failures:
                _put(f"  x {g} :: {name}\n")
                if tb:
                    for line in tb.split("\n"):
                        _put(f"    {line}\n")
                _put("\n")
        _put("\n")


def pytest_configure(config):
    config._live = _LiveReporter()
    config.pluginmanager.register(config._live)



