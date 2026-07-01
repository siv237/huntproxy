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
    """Collect (method, path_pattern) tuples from server.py.

    Routes are registered on ``self._router`` via ``add`` / ``add_prefix``
    calls inside ``HuntServer._register_routes``.  A ``for m in ("GET",
    "POST"):`` loop expands a single registration into one endpoint per
    method (preserving the original any-method behaviour of routes that
    had no ``method ==`` guard).
    """
    src = SERVER_PATH.read_text(encoding="utf-8")
    endpoints = set()
    # Matches: self._router.add("GET", "/api/...", ...) and add_prefix(...)
    # The method token may be a quoted literal or a loop variable (e.g. ``m``).
    add_re = re.compile(
        r'self\._router\.add(?:_prefix)?\(\s*'
        r'([\'"]?[A-Za-z_]+[\'"]?)\s*,\s*'
        r'([\'"])(/[^\'"]+)\2'
    )
    loop_var = None
    loop_methods = []
    loop_indent = None
    for line in src.splitlines():
        indent = len(line) - len(line.lstrip())
        if loop_var is not None and indent <= loop_indent:
            loop_var = None
            loop_methods = []
            loop_indent = None
        mfor = re.match(r'\s*for\s+(\w+)\s+in\s+\(([^)]*)\)\s*:', line)
        if mfor:
            loop_var = mfor.group(1)
            loop_methods = re.findall(r'["\']([A-Z]+)["\']', mfor.group(2))
            loop_indent = indent
            continue
        m = add_re.search(line)
        if not m:
            continue
        method_tok = m.group(1)
        path = m.group(3)
        if not path.startswith("/api/"):
            continue
        if method_tok.startswith(("'", '"')):
            endpoints.add((method_tok.strip("'\""), path))
        elif loop_var is not None and method_tok == loop_var:
            for mv in loop_methods:
                endpoints.add((mv, path))
        else:
            endpoints.add(("ANY", path))
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
