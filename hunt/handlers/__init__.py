"""HTTP handler domain modules — split from the former HuntServer monolith.

Each module owns a focused group of ``_handle_*`` methods.  Handler classes
are constructed with ``(state, server=None)`` and wired into ``HuntServer``
via :meth:`HuntServer._register_routes`.
"""

from urllib.parse import unquote


def _qs(path: str) -> dict:
    params = {}
    if "?" in path:
        for p in path.split("?", 1)[1].split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = unquote(v)
    return params
