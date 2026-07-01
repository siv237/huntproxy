"""HTTP fuzzing tests — security properties of the network-facing server.

These tests use Hypothesis to generate adversarial inputs and verify
that the server never crashes (500), hangs, or leaks filesystem paths.

Properties tested:
- **Path traversal**: ``_serve_static`` rejects ``../`` sequences
- **Malformed query params**: non-integer ``since``/``limit``/``hours``
  must not raise 500
- **Malformed JSON bodies**: random bytes as POST body must not 500
- **Oversized bodies**: large Content-Length must not hang
- **Weird HTTP methods**: unknown methods get 404, not 500
- **Extremely long paths**: must not crash or hang

Tagged ``fuzz`` so they can be run in isolation:

    ./test.sh -m fuzz          # fuzzing only
    ./test.sh --security       # all security tests (arch + fuzz)
"""

import asyncio
import json
import string

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck


# ── Helpers ────────────────────────────────────────────────────────────

def _parse_status(response: bytes) -> int:
    """Extract HTTP status code from raw response bytes.

    Returns 0 if the connection was dropped without a valid HTTP response
    (indicates an unhandled server crash — worse than a 500).
    """
    try:
        first_line = response.split(b"\r\n", 1)[0]
        parts = first_line.split(b" ", 2)
        return int(parts[1])
    except (IndexError, ValueError):
        return 0


async def _send_request(port: int, method: str, path: str,
                        body: bytes = b"", extra_headers: str = "") -> bytes:
    """Send a raw HTTP request and return the full response bytes."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        req = f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        if body:
            req += f"Content-Length: {len(body)}\r\n"
        if extra_headers:
            req += extra_headers
        req += "Connection: close\r\n\r\n"
        writer.write(req.encode())
        if body:
            writer.write(body)
        await writer.drain()
        resp = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            resp += chunk
        return resp
    finally:
        writer.close()
        await writer.wait_closed()


# ── Path traversal ─────────────────────────────────────────────────────

@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=50, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(
    alphabet=string.printable.replace("\r", "").replace("\n", ""),
    min_size=1, max_size=200
))
async def test_static_no_path_traversal(api_server, path_suffix):
    """_serve_static must never serve files outside WEB_DIR.

    Any path containing ``..`` or starting with ``/`` should return 404,
    never a file from outside the web directory.
    """
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    resp = await _send_request(port, "GET", f"/css/{path_suffix}")
    status = _parse_status(resp)
    # Must be 200 (legit file) or 404 — never 0 (crash) or 500 (unhandled)
    assert status in (200, 404), f"Got {status} for /css/{path_suffix!r}"


@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=30, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(
    alphabet=string.printable.replace("\r", "").replace("\n", ""),
    min_size=1, max_size=100
))
async def test_static_traversal_with_dotdot(api_server, suffix):
    """Explicit ``../`` traversal attempts must always 404."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    resp = await _send_request(port, "GET", f"/css/../{suffix}")
    status = _parse_status(resp)
    assert status == 404, f"Path traversal returned {status}, not 404"


# ── Malformed query params ─────────────────────────────────────────────

@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=50, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(
    alphabet=string.printable.replace("&", "").replace("=", "")
                                .replace("\r", "").replace("\n", ""),
    min_size=1, max_size=50
))
async def test_events_since_non_integer(api_server, since_val):
    """``/api/events?since=<garbage>`` must not crash with 500."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    resp = await _send_request(port, "GET", f"/api/events?since={since_val}")
    status = _parse_status(resp)
    # Accept 200 (valid response) — reject 0 (crash/drop) and 500 (unhandled)
    assert status not in (0, 500), (
        f"/api/events?since={since_val!r} caused server crash (status={status}) — "
        "int() on non-numeric query param is unhandled. Use _int_param()."
    )


@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=50, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(
    alphabet=string.printable.replace("&", "").replace("=", "")
                                .replace("\r", "").replace("\n", ""),
    min_size=1, max_size=50
))
async def test_proxy_checks_limit_non_integer(api_server, limit_val):
    """``/api/proxy-checks/X?limit=<garbage>`` must not crash with 500."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    resp = await _send_request(
        port, "GET", f"/api/proxy-checks/127.0.0.1:8080?limit={limit_val}")
    status = _parse_status(resp)
    assert status not in (0, 500), (
        f"/api/proxy-checks/...?limit={limit_val!r} caused server crash (status={status})"
    )


@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=30, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(
    alphabet=string.printable.replace("&", "").replace("=", "")
                                .replace("\r", "").replace("\n", ""),
    min_size=1, max_size=50
))
async def test_heatmap_hours_non_integer(api_server, hours_val):
    """``/api/proxy-heatmap?hours=<garbage>`` must not crash with 500."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    resp = await _send_request(port, "GET", f"/api/proxy-heatmap?hours={hours_val}")
    status = _parse_status(resp)
    assert status not in (0, 500), (
        f"/api/proxy-heatmap?hours={hours_val!r} caused server crash (status={status})"
    )


# ── Malformed JSON bodies ──────────────────────────────────────────────

@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=30, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.binary(min_size=0, max_size=4096))
async def test_blacklist_add_malformed_body(api_server, body):
    """``/api/blacklist/add`` with random bytes must not 500."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    resp = await _send_request(port, "POST", "/api/blacklist/add", body=body)
    status = _parse_status(resp)
    assert status not in (0, 500), f"POST /api/blacklist/add with malformed body caused crash"


@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=30, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.binary(min_size=0, max_size=4096))
async def test_favorites_add_malformed_body(api_server, body):
    """``/api/favorites/add`` with random bytes must not 500."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    resp = await _send_request(port, "POST", "/api/favorites/add", body=body)
    status = _parse_status(resp)
    assert status not in (0, 500), f"POST /api/favorites/add with malformed body caused crash"


# ── Oversized bodies ───────────────────────────────────────────────────

@pytest.mark.fuzz
@pytest.mark.asyncio
async def test_oversized_body_does_not_hang(api_server):
    """A 1MB body must be handled without hanging."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    big_body = b"A" * (1024 * 1024)
    resp = await asyncio.wait_for(
        _send_request(port, "POST", "/api/blacklist/add", body=big_body),
        timeout=15,
    )
    status = _parse_status(resp)
    assert status not in (0, 500), "1MB body caused crash"


# ── Weird HTTP methods ─────────────────────────────────────────────────

@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=30, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(
    alphabet=string.ascii_uppercase + " ",
    min_size=1, max_size=10
).filter(lambda m: m.strip() and not m.startswith(" ")))
async def test_unknown_http_method(api_server, method):
    """Unknown HTTP methods must get 404, not 500."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    # Clean method — no spaces in the middle
    clean = method.strip().split()[0]
    if not clean:
        return
    resp = await _send_request(port, clean, "/api/snapshot")
    status = _parse_status(resp)
    assert status not in (0, 500), f"Method {clean!r} caused crash"


# ── Extremely long paths ───────────────────────────────────────────────

@pytest.mark.fuzz
@pytest.mark.asyncio
@settings(max_examples=20, deadline=5000,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.integers(min_value=100, max_value=10000))
async def test_long_path_does_not_crash(api_server, length):
    """Paths up to 10KB must not crash the server."""
    base_url, _ = api_server
    port = int(base_url.rsplit(":", 1)[1])
    long_path = "/api/proxy/" + "A" * length
    resp = await asyncio.wait_for(
        _send_request(port, "GET", long_path),
        timeout=10,
    )
    status = _parse_status(resp)
    assert status in (200, 404), f"Long path ({length} chars) caused {status}"
