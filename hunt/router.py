"""HTTP route registry — replaces the monolithic if/elif dispatch in HuntServer.

Routes are registered as ``(method, pattern, handler)`` tuples.  This makes
the routing layer Open/Closed: adding a new endpoint means registering a
handler, not editing a 1000-line if/elif chain.

Usage::

    router = Router()
    router.add("GET", "/api/snapshot", handle_snapshot)
    router.add("POST", "/api/hunt/start", handle_hunt_start)
    router.add_prefix("GET", "/api/events", handle_events)  # /api/events?since=…

    handler, match_info = router.match("GET", "/api/snapshot")
    if handler:
        response, status, ct = await handler(server, raw_path, body)
"""

from typing import Any, Callable, Optional


Handler = Callable[..., Any]


class Router:
    """Pattern-matching route dispatcher.

    Supports two match modes:
    - **Exact**: ``add("GET", "/api/snapshot", handler)`` — path must equal
      the pattern exactly (query string already stripped by the caller).
    - **Prefix**: ``add_prefix("POST", "/api/schedules/", handler)`` — path
      must start with the prefix.  Prefix routes are checked *after* exact
      routes, longest prefix first, so ``/api/schedules/status`` (exact)
      wins over ``/api/schedules/`` (prefix).
    """

    def __init__(self):
        self._exact: dict[tuple[str, str], Handler] = {}
        self._prefix: list[tuple[str, str, Handler]] = []

    def add(self, method: str, path: str, handler: Handler) -> None:
        """Register an exact-match route."""
        self._exact[(method.upper(), path)] = handler

    def add_prefix(self, method: str, prefix: str, handler: Handler) -> None:
        """Register a prefix-match route.  Longer prefixes are matched first."""
        self._prefix.append((method.upper(), prefix, handler))
        self._prefix.sort(key=lambda t: len(t[1]), reverse=True)

    def add_static(self, prefixes: list[str], handler: Handler) -> None:
        """Register a static-file handler for multiple path prefixes.

        Static routes match any method and are checked first.
        """
        for prefix in prefixes:
            self.add_prefix("*", prefix, handler)

    def match(self, method: str, path: str) -> Optional[Handler]:
        """Find the handler for ``(method, path)``.

        Returns the handler callable, or ``None`` if no route matches.
        """
        m = method.upper()

        # 1. Exact match — highest priority.
        handler = self._exact.get((m, path))
        if handler is not None:
            return handler

        # 2. Prefix match — longest prefix first (sorted in add_prefix).
        for pm, prefix, handler in self._prefix:
            if path.startswith(prefix) and (pm == "*" or pm == m):
                return handler

        return None
