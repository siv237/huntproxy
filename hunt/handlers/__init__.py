"""HTTP handler domain modules — split from the former HuntServer monolith.

Each module owns a focused group of ``_handle_*`` methods.  Handler classes
are constructed with ``(state, server=None)`` and wired into ``HuntServer``
via :meth:`HuntServer._register_routes`.
"""

from urllib.parse import unquote
import json


def _qs(path: str) -> dict:
    params = {}
    if "?" in path:
        for p in path.split("?", 1)[1].split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = unquote(v)
    return params


def _int_param(qs: dict, key: str, default: int) -> int:
    """Parse an integer query param, returning *default* on invalid input."""
    raw = qs.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def _json_body(body) -> dict:
    """Parse a JSON request body, returning ``{}`` on invalid/non-dict input."""
    try:
        data = json.loads(body or b"{}")
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return data
