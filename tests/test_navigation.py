"""Verify navigation consistency: every nav button has a registered route
and a title entry, every registered route has a nav button, and every
title entry has a matching route.

This prevents dead-end buttons, orphaned routes, and missing page titles
after refactoring.
"""
import re
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _nav_pages():
    """All data-page values in index.html (sidebar nav buttons)."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    return set(re.findall(r'data-page="([^"]+)"', html))


def _registered_routes():
    """All router.register('name', ...) calls in JS."""
    routes = set()
    for js in (WEB_DIR / "js").rglob("*.js"):
        src = js.read_text(encoding="utf-8")
        routes |= set(re.findall(r"router\.register\(['\"]([^'\"]+)", src))
    return routes


def _router_titles():
    """All keys in router.titles object."""
    src = (WEB_DIR / "js" / "router.js").read_text(encoding="utf-8")
    titles = set()
    in_titles = False
    for line in src.splitlines():
        if "titles:" in line:
            in_titles = True
            continue
        if in_titles:
            m = re.match(r"^\s*'?([a-zA-Z'\-]+)'?:\s*\[", line)
            if m:
                titles.add(m.group(1).strip("'"))
            elif line.strip() == "},":
                break
    return titles


def _script_srcs():
    """All <script src="/js/pages/..."> includes in index.html."""
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    return set(re.findall(r'<script src="/js/pages/([^"]+)\.js', html))


class TestNavigationConsistency:
    def test_every_nav_button_has_route(self):
        """Every data-page button must have a matching registered route."""
        nav = _nav_pages()
        routes = _registered_routes()
        missing = sorted(nav - routes)
        assert not missing, (
            f"Nav buttons without registered routes: {missing}"
        )

    def test_every_nav_button_has_title(self):
        """Every data-page button must have a router.titles entry."""
        nav = _nav_pages()
        titles = _router_titles()
        missing = sorted(nav - titles)
        assert not missing, (
            f"Nav buttons without router.titles: {missing}"
        )

    def test_every_route_has_nav_button(self):
        """Every registered route should have a nav button (unless it's
        a sub-page that's intentionally not in the sidebar)."""
        nav = _nav_pages()
        routes = _registered_routes()
        orphaned = sorted(routes - nav)
        # proxy-card is a component, not a navigable page
        orphaned = [r for r in orphaned if r != "proxy-card"]
        assert not orphaned, (
            f"Registered routes without nav buttons: {orphaned}"
        )

    def test_every_title_has_route(self):
        """Every router.titles entry must have a matching registered route."""
        titles = _router_titles()
        routes = _registered_routes()
        missing = sorted(titles - routes)
        assert not missing, (
            f"router.titles entries without routes: {missing}"
        )

    def test_every_route_page_script_is_included(self):
        """Every router.register call should have a matching <script> tag
        in index.html, otherwise the page won't load."""
        routes = _registered_routes()
        scripts = _script_srcs()
        # proxy-card is a component, not a navigable page
        routes = {r for r in routes if r != "proxy-card"}
        # Some route names don't match their script filename (e.g. 'api'
        # is registered in api-docs.js). Check that for each route there
        # exists a script whose router.register call uses that name.
        route_to_script = {}
        for js in (WEB_DIR / "js" / "pages").glob("*.js"):
            src = js.read_text(encoding="utf-8")
            for m in re.findall(r"router\.register\(['\"]([^'\"]+)", src):
                route_to_script[m] = js.stem
        missing = sorted(r for r in routes if r not in route_to_script)
        # Verify the script file is actually included in index.html
        not_included = sorted(
            route_to_script[r]
            for r in routes
            if r in route_to_script and route_to_script[r] not in scripts
        )
        assert not missing, f"Routes without a page script: {missing}"
        assert not not_included, (
            f"Page scripts not included in index.html: {not_included}"
        )
