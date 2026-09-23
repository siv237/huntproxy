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

    async def _handle_pool_countries_get(self, raw_path, body):
        return json.dumps(self._pool_countries_payload()), 200, "application/json"

    async def _handle_pool_countries_set(self, raw_path, body):
        data = _json_body(body)
        policy = self.state.set_pool_country_policy(
            str(data.get("mode", "off")), data.get("countries", []))
        if not policy.get("persisted", True):
            return json.dumps({"error": "country policy was not persisted"}), 500, "application/json"
        self.state._log_action("pool.countries", f"{policy['mode']}:{','.join(policy['countries'])}")
        return json.dumps(self._pool_countries_payload()), 200, "application/json"

    def _pool_countries_payload(self) -> dict:
        payload = self.state.get_pool_country_policy()
        payload["available"] = self.state.get_pool_countries()
        payload["warning"] = self._pool_countries_warning(payload)
        return payload

    def _pool_countries_warning(self, payload) -> str:
        """Warn when an allow-list matches no selectable proxy: the pool would
        be empty and every pool/failover connection would fail with 502."""
        if payload["mode"] != "only" or not payload["countries"]:
            return ""
        available = {c["country_code"] for c in payload["available"]}
        if available & set(payload["countries"]):
            return ""
        return "no_proxies_in_selected_countries"

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
