"""Verify that every API call made by the frontend has a matching server
endpoint that accepts the correct HTTP method.

This prevents dead-end buttons and 'not found' errors caused by method
mismatches (e.g. frontend does GET but server only accepts POST) or
missing endpoints after refactoring.
"""
import re
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
SERVER_PATH = Path(__file__).resolve().parent.parent / "hunt" / "server.py"


def _collect_frontend_calls():
    """Collect (method, path) tuples from all frontend JS."""
    calls = set()
    for js in (WEB_DIR / "js").rglob("*.js"):
        src = js.read_text(encoding="utf-8")
        # api.js: this.request('/api/...', 'METHOD', ...) or
        #         this.request('/api/...')  (implicit GET)
        for m in re.finditer(
            r"this\.request\(['\"]([^'\"]+)['\"]"
            r"(?:,\s*['\"]([A-Z]+)['\"])?",
            src,
        ):
            path = m.group(1)
            method = m.group(2) or "GET"
            # Skip paths with template variables like ${...}
            if "${" in path:
                # Normalize: extract base path
                path = re.sub(r"\$\{[^}]+\}", "{var}", path)
            calls.add((method, path, js.name))
        # window.location.href = '/api/...'  (always GET)
        for m in re.finditer(
            r"window\.location\.href\s*=\s*['\"](/api/[^'\"]+)", src
        ):
            calls.add(("GET", m.group(1), js.name))
        # fetch('/api/...', { method: 'POST' })
        for m in re.finditer(
            r"fetch\(['\"](/api/[^'\"]+)['\"],\s*\{[^}]*method:\s*['\"]([A-Z]+)",
            src,
        ):
            calls.add((m.group(2), m.group(1), js.name))
        # fetch('/api/...') without method (implicit GET)
        for m in re.finditer(
            r"fetch\(['\"](/api/[^'\"]+)['\"]\)", src
        ):
            calls.add(("GET", m.group(1), js.name))
    return calls


def _collect_server_endpoints():
    """Collect (method, path_pattern) tuples from server.py."""
    src = SERVER_PATH.read_text(encoding="utf-8")
    endpoints = set()
    for line in src.splitlines():
        line = line.strip()
        # path.startswith("/api/...") or path == "/api/..."
        m = re.search(r'path\.startswith\(\s*["\']([^"\']+)["\']\s*\)', line)
        if not m:
            m = re.search(r'path\s*==\s*["\']([^"\']+)["\']', line)
        if not m:
            continue
        path = m.group(1)
        if not path.startswith("/api/"):
            continue
        # method check on same line
        m2 = re.search(r'method\s*==\s*["\']([A-Z]+)["\']', line)
        method = m2.group(1) if m2 else "ANY"
        endpoints.add((method, path))
    return endpoints


def _path_matches(pattern, path):
    """Check if a concrete path matches a server path pattern.

    Server uses startswith() so /api/proxy/ matches /api/proxy/1.2.3.4:80.
    For exact == patterns, the path must match exactly.
    startswith patterns ending with / match sub-paths; those without /
    match exact or sub-paths.
    """
    if path == pattern:
        return True
    if path.startswith(pattern):
        return True
    # startswith("/api/foo/") won't match "/api/foo" (no trailing slash),
    # but there's usually a separate exact handler for the base path.
    return False


def _find_matching_endpoint(method, path, server_endpoints):
    """Find a server endpoint that matches the given method+path."""
    for srv_method, srv_pattern in server_endpoints:
        if not _path_matches(srv_pattern, path):
            continue
        # Check method compatibility
        if srv_method == "ANY":
            return (srv_method, srv_pattern)
        if srv_method == method:
            return (srv_method, srv_pattern)
    return None


@pytest.fixture(scope="module")
def frontend_calls():
    return _collect_frontend_calls()


@pytest.fixture(scope="module")
def server_endpoints():
    return _collect_server_endpoints()


class TestApiConsistency:
    @pytest.mark.parametrize(
        "method,path,source",
        sorted(_collect_frontend_calls()),
    )
    def test_frontend_call_has_server_endpoint(
        self, method, path, source, server_endpoints
    ):
        """Every API call from the frontend must have a matching server
        endpoint that accepts the correct HTTP method."""
        match = _find_matching_endpoint(method, path, server_endpoints)
        assert match is not None, (
            f"{source}: {method} {path} has no matching server endpoint. "
            f"The button/action will get 'not found'."
        )

    def test_server_endpoints_nonempty(self, server_endpoints):
        """Sanity check: server endpoints were actually parsed."""
        assert len(server_endpoints) > 20, (
            f"Only found {len(server_endpoints)} endpoints, "
            "parsing may be broken"
        )

    def test_no_duplicate_server_endpoints(self, server_endpoints):
        """No two server endpoints should have the same (method, path).

        Duplicates cause unreachable code — only the first match wins.
        This catches copy-paste errors like the old double /api/schedules/*/run.
        """
        seen = {}
        dups = []
        for method, path in sorted(server_endpoints):
            key = (method, path)
            if key in seen:
                dups.append(key)
            seen[key] = True
        assert not dups, f"Duplicate server endpoints: {dups}"
