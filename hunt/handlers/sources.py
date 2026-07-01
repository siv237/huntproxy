"""Source handlers — proxy-sources, ip-blacklists, blocklists, custom-proxies CRUD."""

import json
from urllib.parse import unquote

from hunt.constants import logger
from hunt.handlers import _qs


class SourceHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    # === Proxy Sources API ===

    async def _handle_proxy_sources_list(self, raw_path, body):
        sources = self.state.get_proxy_sources()
        return json.dumps({"sources": sources}), 200, "application/json"

    async def _handle_proxy_source_create(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.create_proxy_source(data)
        if result:
            return json.dumps({"ok": True, "source": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "id, name and url are required"}), 400, "application/json"

    async def _handle_proxy_sources_fetch(self, raw_path, body):
        if getattr(self.state, '_fetching_sources', False):
            return json.dumps({"ok": False, "error": "fetch already in progress"}), 409, "application/json"
        self.state._fetching_sources = True
        try:
            seen = await self.state._download_sources()
            self.state._update_source_stats()
            sources = self.state.get_proxy_sources()
            results = []
            for s in sources:
                if not s.get("enabled"):
                    continue
                results.append({
                    "id": s["id"],
                    "name": s.get("name", s["id"]),
                    "status": s.get("last_fetch_status", ""),
                    "count": s.get("last_fetch_count", 0),
                    "error": s.get("last_fetch_error", ""),
                })
            return json.dumps({"ok": True, "total_addresses": len(seen), "sources": results}), 200, "application/json"
        except Exception as e:
            logger.error("proxy-sources/fetch: %s", e)
            return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"
        finally:
            self.state._fetching_sources = False

    async def _handle_proxy_sources_progress(self, raw_path, body):
        return json.dumps({"progress": self.state.get_proxy_source_fetch_progress()}), 200, "application/json"

    async def _handle_proxy_source_get(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/proxy-sources/"):])
        result = self.state.get_proxy_source(source_id)
        if result:
            return json.dumps(result), 200, "application/json"
        return json.dumps({"error": "not found"}), 404, "application/json"

    async def _handle_proxy_source_post(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            source_id = unquote(path[len("/api/proxy-sources/"):-len("/toggle")])
            result = self.state.toggle_proxy_source(source_id)
            if result:
                return json.dumps({"ok": True, "source": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/proxy-sources/"):])
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.update_proxy_source(source_id, data)
        if result:
            return json.dumps({"ok": True, "source": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    async def _handle_proxy_source_delete(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/proxy-sources/"):])
        ok = self.state.delete_proxy_source(source_id)
        if ok:
            return json.dumps({"ok": True}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    # === IP Blacklist Sources API ===

    async def _handle_ip_blacklists_list(self, raw_path, body):
        sources = self.state.get_ip_blacklist_sources()
        return json.dumps({"sources": sources}), 200, "application/json"

    async def _handle_ip_blacklist_create(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.create_ip_blacklist_source(data)
        if result:
            return json.dumps({"ok": True, "source": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "id, name and url are required"}), 400, "application/json"

    async def _handle_ip_blacklists_fetch(self, raw_path, body):
        if getattr(self.state, '_fetching_ip_blacklists', False):
            return json.dumps({"ok": False, "error": "fetch already in progress"}), 409, "application/json"
        self.state._fetching_ip_blacklists = True
        try:
            results = await self.state._download_ip_blacklists()
            total = sum(results.values())
            return json.dumps({"ok": True, "total_entries": total, "sources": [{"id": k, "count": v} for k, v in results.items()]}), 200, "application/json"
        except Exception as e:
            logger.error("ip-blacklists/fetch: %s", e)
            return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"
        finally:
            self.state._fetching_ip_blacklists = False

    async def _handle_ip_blacklists_progress(self, raw_path, body):
        return json.dumps({"progress": self.state.get_ip_blacklist_fetch_progress()}), 200, "application/json"

    async def _handle_ip_blacklist_get(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle") or path.endswith("/fetch"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/ip-blacklists/"):])
        result = self.state.get_ip_blacklist_source(source_id)
        if result:
            return json.dumps(result), 200, "application/json"
        return json.dumps({"error": "not found"}), 404, "application/json"

    async def _handle_ip_blacklist_post(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            source_id = unquote(path[len("/api/ip-blacklists/"):-len("/toggle")])
            result = self.state.toggle_ip_blacklist_source(source_id)
            if result:
                return json.dumps({"ok": True, "source": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
        if path.endswith("/fetch"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/ip-blacklists/"):])
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.update_ip_blacklist_source(source_id, data)
        if result:
            return json.dumps({"ok": True, "source": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    async def _handle_ip_blacklist_delete(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle") or path.endswith("/fetch"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/ip-blacklists/"):])
        ok = self.state.delete_ip_blacklist_source(source_id)
        if ok:
            return json.dumps({"ok": True}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    async def _handle_ip_blacklist_entries(self, raw_path, body):
        qs = _qs(raw_path)
        page = int(qs.get("page", 1))
        limit = int(qs.get("limit", 50))
        entries = sorted(self.state.ip_blacklist_entries.items())
        total = len(entries)
        start = (page - 1) * limit
        end = start + limit
        page_entries = []
        for entry, metas in entries[start:end]:
            for meta in metas:
                page_entries.append({
                    "entry": entry,
                    "source_id": meta.get("source_id"),
                    "source_name": meta.get("source_name"),
                    "reason": meta.get("reason", ""),
                })
        return json.dumps({"total": total, "page": page, "limit": limit, "entries": page_entries}), 200, "application/json"

    async def _handle_ip_blacklist_matches(self, raw_path, body):
        matches = self.state.get_ip_blacklist_matches()
        return json.dumps({"matches": matches, "total": len(matches)}), 200, "application/json"

    # === Country Blocklists API ===

    async def _handle_blocklists_list(self, raw_path, body):
        sources = self.state.get_blocklist_sources()
        return json.dumps({"sources": sources}), 200, "application/json"

    async def _handle_blocklist_create(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.create_blocklist_source(data)
        if result:
            return json.dumps({"ok": True, "source": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "id, name and url are required"}), 400, "application/json"

    async def _handle_blocklists_fetch(self, raw_path, body):
        if getattr(self.state, '_fetching_blocklists', False):
            return json.dumps({"ok": False, "error": "fetch already in progress"}), 409, "application/json"
        try:
            results = await self.state._download_blocklists()
            total = sum(results.values())
            return json.dumps({"ok": True, "total_entries": total, "sources": [{"id": k, "count": v} for k, v in results.items()]}), 200, "application/json"
        except Exception as e:
            logger.error("blocklists/fetch: %s", e)
            return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"

    async def _handle_blocklists_progress(self, raw_path, body):
        return json.dumps({"progress": self.state.get_blocklist_fetch_progress()}), 200, "application/json"

    async def _handle_blocklist_get(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle") or path.endswith("/fetch"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/blocklists/"):])
        result = self.state.get_blocklist_source(source_id)
        if result:
            return json.dumps(result), 200, "application/json"
        return json.dumps({"error": "not found"}), 404, "application/json"

    async def _handle_blocklist_post(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            source_id = unquote(path[len("/api/blocklists/"):-len("/toggle")])
            result = self.state.toggle_blocklist_source(source_id)
            if result:
                return json.dumps({"ok": True, "source": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
        if path.endswith("/fetch"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/blocklists/"):])
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.update_blocklist_source(source_id, data)
        if result:
            return json.dumps({"ok": True, "source": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    async def _handle_blocklist_delete(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle") or path.endswith("/fetch"):
            return json.dumps({"error": "not found"}), 404, "application/json"
        source_id = unquote(path[len("/api/blocklists/"):])
        ok = self.state.delete_blocklist_source(source_id)
        if ok:
            return json.dumps({"ok": True}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    # === Custom Proxies API ===

    async def _handle_custom_proxies_list(self, raw_path, body):
        proxies = self.state.get_custom_proxies()
        return json.dumps({"proxies": proxies}), 200, "application/json"

    async def _handle_custom_proxy_create(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.create_custom_proxy(data)
        if result:
            return json.dumps({"ok": True, "proxy": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "id, name, host and port are required"}), 400, "application/json"

    async def _handle_custom_proxy_test_direct(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = await self.state.test_proxy_direct(data)
        return json.dumps(result), 200, "application/json"

    async def _handle_custom_proxy_get(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle") or path.endswith("/test") or path == "/api/custom-proxies/test-direct":
            return json.dumps({"error": "not found"}), 404, "application/json"
        proxy_id = unquote(path[len("/api/custom-proxies/"):])
        result = self.state.get_custom_proxy(proxy_id)
        if result:
            return json.dumps(result), 200, "application/json"
        return json.dumps({"error": "not found"}), 404, "application/json"

    async def _handle_custom_proxy_post(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            proxy_id = unquote(path[len("/api/custom-proxies/"):-len("/toggle")])
            result = self.state.toggle_custom_proxy(proxy_id)
            if result:
                return json.dumps({"ok": True, "proxy": result}), 200, "application/json"
            return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
        if path.endswith("/test"):
            proxy_id = unquote(path[len("/api/custom-proxies/"):-len("/test")])
            result = await self.state.test_custom_proxy(proxy_id)
            return json.dumps(result), 200, "application/json"
        proxy_id = unquote(path[len("/api/custom-proxies/"):])
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        result = self.state.update_custom_proxy(proxy_id, data)
        if result:
            return json.dumps({"ok": True, "proxy": result}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"

    async def _handle_custom_proxy_delete(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle") or path.endswith("/test") or path == "/api/custom-proxies/test-direct":
            return json.dumps({"error": "not found"}), 404, "application/json"
        proxy_id = unquote(path[len("/api/custom-proxies/"):])
        ok = self.state.delete_custom_proxy(proxy_id)
        if ok:
            return json.dumps({"ok": True}), 200, "application/json"
        return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
