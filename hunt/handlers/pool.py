"""Pool handlers — manual blacklist and favorites management."""

import json

from hunt.handlers import _qs, _int_param, _json_body


class PoolHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _handle_blacklist_add(self, raw_path, body):
        data = _json_body(body)
        addr = data.get("address", "")
        self.state.blacklist_add(addr, data.get("reason", ""))
        self.state._log_action("blacklist.add", addr)
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_blacklist_remove(self, raw_path, body):
        data = _json_body(body)
        addr = data.get("address", "")
        self.state.blacklist_remove(addr)
        self.state._log_action("blacklist.remove", addr)
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_favorites_add(self, raw_path, body):
        data = _json_body(body)
        addr = data.get("address", "")
        self.state.favorite_add(addr)
        self.state._log_action("favorites.add", addr)
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_favorites_remove(self, raw_path, body):
        data = _json_body(body)
        addr = data.get("address", "")
        self.state.favorite_remove(addr)
        self.state._log_action("favorites.remove", addr)
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_favorites_list(self, raw_path, body):
        favs = [r for r in self.state.ratings.values() if r.is_favorite]
        favs.sort(key=lambda r: r.score, reverse=True)
        return json.dumps([r.to_dict() for r in favs]), 200, "application/json"

    async def _handle_blacklist_list(self, raw_path, body):
        qs = _qs(raw_path)
        page = _int_param(qs, "page", 1)
        limit = _int_param(qs, "limit", 20)
        bl = self.state._blacklist_view()
        total = len(bl)
        start = (page - 1) * limit
        end = start + limit
        return json.dumps({
            "total": total,
            "page": page,
            "limit": limit,
            "blacklist": bl[start:end],
        }), 200, "application/json"
