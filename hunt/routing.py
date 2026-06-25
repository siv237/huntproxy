"""Functional split of the huntproxy backend."""

import time
from hunt.constants import logger
from typing import Optional

class RoutingMixin:
    def _routing_get(self, key: str, default: str = "") -> str:
            try:
                conn = self._db()
                row = conn.execute("SELECT value FROM routing_config WHERE key=?", (key,)).fetchone()
                conn.close()
                return row["value"] if row else default
            except Exception:
                return default

    def _routing_set(self, key: str, value: str):
            try:
                conn = self._db()
                conn.execute("INSERT OR REPLACE INTO routing_config (key, value) VALUES (?,?)", (key, value))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error("routing_set: %s", e)

    def get_routing_status(self) -> dict:
            enabled = self._routing_get("routing_enabled", "false") == "true"
            default_route = self._routing_get("default_route", "direct")
            lists = self.get_domain_lists()
            return {
                "enabled": enabled,
                "default_route": default_route,
                "lists": lists,
                "custom_proxies": self.get_custom_proxies(),
            }

    def routing_enable(self):
            self._routing_set("routing_enabled", "true")
            self._emit("Routing enabled", "info")

    def routing_disable(self):
            self._routing_set("routing_enabled", "false")
            self._emit("Routing disabled", "info")

    def routing_set_default(self, route: str):
            self._routing_set("default_route", route)
            self._emit(f"Default route set to: {route}", "info")

    def routing_test(self, domain: str) -> dict:
            enabled = self._routing_get("routing_enabled", "false") == "true"
            if not enabled:
                if hasattr(self, 'proxy_runner') and self.proxy_runner:
                    if self.proxy_runner.direct_mode:
                        return {"domain": domain, "route": "direct", "matched_list": None, "routing_enabled": False}
                    if self.proxy_runner.active_proxy_addr:
                        return {"domain": domain, "route": f"proxy:{self.proxy_runner.active_proxy_addr}", "matched_list": None, "routing_enabled": False}
                return {"domain": domain, "route": "pool", "matched_list": None, "routing_enabled": False}

            default_route = self._routing_get("default_route", "direct")
            conn = self._db()
            try:
                rows = conn.execute(
                    "SELECT dl.id, dl.name, dl.route FROM domain_lists dl "
                    "WHERE dl.enabled=1 AND dl.route!='' ORDER BY dl.priority ASC"
                ).fetchall()
                for row in rows:
                    patterns = conn.execute(
                        "SELECT pattern FROM domain_entries WHERE list_id=?",
                        (row["id"],)
                    ).fetchall()
                    if self._domain_matches(domain, [p["pattern"] for p in patterns]):
                        return {"domain": domain, "route": row["route"], "matched_list": row["name"], "routing_enabled": True}
            finally:
                conn.close()
            return {"domain": domain, "route": default_route, "matched_list": None, "routing_enabled": True}

    def get_domain_lists(self) -> list:
            try:
                conn = self._db()
                rows = conn.execute(
                    "SELECT dl.id, dl.name, dl.source, dl.url, dl.route, dl.enabled, dl.priority, dl.created_at, dl.updated_at, "
                    "(SELECT COUNT(*) FROM domain_entries WHERE list_id=dl.id) as domain_count "
                    "FROM domain_lists dl ORDER BY dl.priority ASC"
                ).fetchall()
                conn.close()
                return [dict(r) for r in rows]
            except Exception as e:
                logger.error("get_domain_lists: %s", e)
                return []

    def get_domain_list(self, list_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute(
                    "SELECT dl.id, dl.name, dl.source, dl.url, dl.route, dl.enabled, dl.priority, dl.created_at, dl.updated_at, "
                    "(SELECT COUNT(*) FROM domain_entries WHERE list_id=dl.id) as domain_count "
                    "FROM domain_lists dl WHERE dl.id=?", (list_id,)
                ).fetchone()
                if not row:
                    conn.close()
                    return None
                patterns = conn.execute(
                    "SELECT pattern FROM domain_entries WHERE list_id=? ORDER BY id", (list_id,)
                ).fetchall()
                conn.close()
                result = dict(row)
                result["domains"] = [p["pattern"] for p in patterns]
                return result
            except Exception as e:
                logger.error("get_domain_list: %s", e)
                return None

    def create_domain_list(self, data: dict) -> Optional[dict]:
            list_id = data.get("id", "").strip()
            name = data.get("name", "").strip()
            if not list_id or not name:
                return None
            domains = data.get("domains", [])
            now = time.time()
            try:
                conn = self._db()
                max_pri = conn.execute("SELECT COALESCE(MAX(priority),-1)+1 as next FROM domain_lists").fetchone()
                priority = max_pri["next"] if max_pri else 0
                conn.execute(
                    "INSERT INTO domain_lists (id, name, source, url, route, enabled, priority, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (list_id, name, data.get("source", "manual"), data.get("url", ""), data.get("route", ""),
                     1 if data.get("enabled", True) else 0, priority, now, now)
                )
                for pattern in domains:
                    p = pattern.strip().lower()
                    if p:
                        conn.execute("INSERT OR IGNORE INTO domain_entries (list_id, pattern) VALUES (?,?)", (list_id, p))
                conn.commit()
                conn.close()
                self._emit(f"Domain list created: {name} ({len(domains)} domains)", "info")
                return self.get_domain_list(list_id)
            except Exception as e:
                logger.error("create_domain_list: %s", e)
                return None

    def update_domain_list(self, list_id: str, data: dict) -> Optional[dict]:
            now = time.time()
            try:
                conn = self._db()
                existing = conn.execute("SELECT source, url FROM domain_lists WHERE id=?", (list_id,)).fetchone()
                if not existing:
                    conn.close()
                    return None
                name = data.get("name", "").strip()
                if name:
                    source = data.get("source", "") or existing["source"] or "manual"
                    url = data.get("url", "") if "url" in data else existing["url"]
                    conn.execute(
                        "UPDATE domain_lists SET name=?, source=?, url=?, route=?, enabled=?, updated_at=? WHERE id=?",
                        (name, source, url, data.get("route", ""),
                         1 if data.get("enabled", True) else 0, now, list_id)
                    )
                if "domains" in data:
                    conn.execute("DELETE FROM domain_entries WHERE list_id=?", (list_id,))
                    for pattern in data["domains"]:
                        p = pattern.strip().lower() if isinstance(pattern, str) else str(pattern).strip().lower()
                        if p:
                            conn.execute("INSERT OR IGNORE INTO domain_entries (list_id, pattern) VALUES (?,?)", (list_id, p))
                conn.commit()
                conn.close()
                self._emit(f"Domain list updated: {list_id}", "info")
                return self.get_domain_list(list_id)
            except Exception as e:
                logger.error("update_domain_list: %s", e)
                return None

    def delete_domain_list(self, list_id: str) -> bool:
            try:
                conn = self._db()
                conn.execute("DELETE FROM domain_entries WHERE list_id=?", (list_id,))
                conn.execute("DELETE FROM domain_lists WHERE id=?", (list_id,))
                conn.commit()
                conn.close()
                self._emit(f"Domain list deleted: {list_id}", "warn")
                return True
            except Exception as e:
                logger.error("delete_domain_list: %s", e)
                return False

    def toggle_domain_list(self, list_id: str) -> Optional[dict]:
            try:
                conn = self._db()
                row = conn.execute("SELECT enabled FROM domain_lists WHERE id=?", (list_id,)).fetchone()
                if not row:
                    conn.close()
                    return None
                new_val = 0 if row["enabled"] else 1
                conn.execute("UPDATE domain_lists SET enabled=?, updated_at=? WHERE id=?", (new_val, time.time(), list_id))
                conn.commit()
                conn.close()
                status = "enabled" if new_val else "disabled"
                self._emit(f"Domain list {list_id} {status}", "info")
                return self.get_domain_list(list_id)
            except Exception as e:
                logger.error("toggle_domain_list: %s", e)
                return None

    def reorder_domain_lists(self, order: list):
            try:
                conn = self._db()
                for i, list_id in enumerate(order):
                    conn.execute("UPDATE domain_lists SET priority=? WHERE id=?", (i, list_id))
                conn.commit()
                conn.close()
                self._emit("Routes reordered", "info")
            except Exception as e:
                logger.error("reorder_domain_lists: %s", e)

    def _resolve_route(self, host: str) -> str:
            enabled = self._routing_get("routing_enabled", "false") == "true"
            if not enabled:
                if hasattr(self, 'proxy_runner') and self.proxy_runner:
                    if self.proxy_runner.direct_mode:
                        return "direct"
                    if self.proxy_runner.active_proxy_addr:
                        return f"proxy:{self.proxy_runner.active_proxy_addr}"
                return "pool"

            conn = self._db()
            try:
                rows = conn.execute(
                    "SELECT dl.id, dl.route FROM domain_lists dl "
                    "WHERE dl.enabled=1 AND dl.route!='' ORDER BY dl.priority ASC"
                ).fetchall()
                for row in rows:
                    patterns = conn.execute(
                        "SELECT pattern FROM domain_entries WHERE list_id=?",
                        (row["id"],)
                    ).fetchall()
                    if self._domain_matches(host, [p["pattern"] for p in patterns]):
                        return row["route"]
            except Exception as e:
                logger.error("_resolve_route: %s", e)
            finally:
                conn.close()
            return self._routing_get("default_route", "direct")

    @staticmethod
    def _domain_matches(host: str, patterns: list) -> bool:
            host_lower = host.lower()
            for pattern in patterns:
                p = pattern.lower().strip()
                if p.startswith("exact:"):
                    if host_lower == p[6:]:
                        return True
                elif p.startswith("*."):
                    suffix = p[1:]
                    if host_lower.endswith(suffix) or host_lower == p[2:]:
                        return True
                elif p.startswith("."):
                    if host_lower.endswith(p) or host_lower == p[1:]:
                        return True
                else:
                    if host_lower == p or host_lower.endswith("." + p):
                        return True
            return False
