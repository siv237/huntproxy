"""Routing handlers — routing status/enable/disable/default/reorder/test, domain-lists CRUD."""

import json
from urllib.parse import unquote


class RoutingHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    # === Routing API ===

    async def _handle_routing_status(self, raw_path, body):
        return json.dumps(self.state.get_routing_status()), 200, "application/json"

    async def _handle_routing_enable(self, raw_path, body):
        self.state.routing_enable()
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_routing_disable(self, raw_path, body):
        self.state.routing_disable()
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_routing_default(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        route = data.get("default_route", "direct")
        self.state.routing_set_default(route)
        return json.dumps({"ok": True, "default_route": route}), 200, "application/json"

    async def _handle_routing_reorder(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        order = data.get("order", [])
        if order:
            self.state.reorder_domain_lists(order)
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_routing_test(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        domain = data.get("domain", "").strip()
        if not domain:
            return json.dumps({"error": "domain is required"}), 400, "application/json"
        result = self.state.routing_test(domain)
        return json.dumps(result), 200, "application/json"

    # === Domain Lists API ===

    async def _handle_domain_lists_list(self, raw_path, body):
        lists = self.state.get_domain_lists()
        return json.dumps({"lists": lists}), 200, "application/json"

    async def _handle_domain_list_create(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.create_domain_list(data)
        if result:
            return json.dumps({"ok": True, "list": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "id and name are required"}), 400, "application/json"

    async def _handle_domain_list_get(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        list_id = unquote(path[len("/api/domain-lists/"):])
        result = self.state.get_domain_list(list_id)
        if result:
            return json.dumps(result), 200, "application/json"
        return json.dumps({"error": "not found"}), 404, "application/json"

    async def _handle_domain_list_post(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            list_id = unquote(path[len("/api/domain-lists/"):-len("/toggle")])
            result = self.state.toggle_domain_list(list_id)
            if result:
                return json.dumps({"ok": True, "list": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
        list_id = unquote(path[len("/api/domain-lists/"):])
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.update_domain_list(list_id, data)
        if result:
            return json.dumps({"ok": True, "list": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    async def _handle_domain_list_delete(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        list_id = unquote(path[len("/api/domain-lists/"):])
        ok = self.state.delete_domain_list(list_id)
        if ok:
            return json.dumps({"ok": True}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
