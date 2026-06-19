"""Functional split of the huntproxy backend."""

import json
import time
from hunt.constants import logger


# Logical groups of tables the user can select for backup/restore.
# Each group maps to (db_attr, table_name) tuples so backup works across
# both state.db and stats.db.
BACKUP_GROUPS = {
    "ratings": {
        "label": "Ratings & working proxies",
        "tables": [("state", "ratings"), ("state", "working_proxies")],
    },
    "blacklist": {
        "label": "Manual blacklist",
        "tables": [("state", "blacklist")],
    },
    "ip_blacklist": {
        "label": "Downloaded IP blacklist",
        "tables": [("state", "ip_blacklist_entries"), ("state", "ip_blacklist_sources")],
    },
    "proxy_sources": {
        "label": "Proxy sources",
        "tables": [("state", "proxy_sources"), ("state", "proxy_source_entries")],
    },
    "routing": {
        "label": "Domain lists & routing",
        "tables": [("state", "domain_lists"), ("state", "domain_entries"), ("state", "routing_config")],
    },
    "custom_proxies": {
        "label": "Custom proxies",
        "tables": [("state", "custom_proxies")],
    },
    "runtime_state": {
        "label": "Runtime state",
        "tables": [("state", "runtime_state")],
    },
    "history": {
        "label": "History stats",
        "tables": [("stats", "history")],
    },
    "traffic_log": {
        "label": "Traffic log",
        "tables": [("stats", "traffic_log")],
    },
    "events": {
        "label": "Events log",
        "tables": [("stats", "events")],
    },
    "actions": {
        "label": "Action log",
        "tables": [("stats", "actions")],
    },
    "canary_history": {
        "label": "Canary history",
        "tables": [("stats", "canary_history")],
    },
}


class BackupMixin:

    def get_backup_groups(self) -> list:
            """Return group metadata with live row counts for the UI."""
            result = []
            for key, info in BACKUP_GROUPS.items():
                total = 0
                tables = []
                for db_attr, table in info["tables"]:
                    try:
                        conn = self._stats_db() if db_attr == "stats" else self._db()
                        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        conn.close()
                        total += n
                        tables.append({"db": db_attr, "table": table, "count": n})
                    except Exception as e:
                        logger.warning(f"backup group {key}.{table}: {e}")
                        tables.append({"db": db_attr, "table": table, "count": 0})
                result.append({"key": key, "label": info["label"], "total": total, "tables": tables})
            return result

    def create_backup(self, selected_groups: list) -> bytes:
            """Create a JSON backup containing the selected groups."""
            backup = {
                "format": "huntproxy-backup",
                "version": 1,
                "created_at": time.time(),
                "groups": {},
            }
            for gkey in selected_groups:
                info = BACKUP_GROUPS.get(gkey)
                if not info:
                    continue
                group_data = {}
                for db_attr, table in info["tables"]:
                    conn = None
                    try:
                        conn = self._stats_db() if db_attr == "stats" else self._db()
                        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                        group_data[table] = [dict(r) for r in rows]
                    except Exception as e:
                        logger.warning(f"backup {gkey}.{table}: {e}")
                        group_data[table] = []
                    finally:
                        if conn is not None:
                            try:
                                conn.close()
                            except Exception:
                                pass
                backup["groups"][gkey] = group_data
            return json.dumps(backup, ensure_ascii=False).encode()

    def restore_backup(self, data: bytes, selected_groups: list) -> dict:
            """Restore selected groups from a backup JSON. Returns per-group counts."""
            try:
                backup = json.loads(data)
            except Exception as e:
                return {"ok": False, "error": f"invalid backup file: {e}"}
            if backup.get("format") != "huntproxy-backup":
                return {"ok": False, "error": "not a huntproxy backup file"}
            groups = backup.get("groups", {})
            restored = {}
            for gkey in selected_groups:
                info = BACKUP_GROUPS.get(gkey)
                if not info:
                    continue
                group_data = groups.get(gkey, {})
                gcount = 0
                for db_attr, table in info["tables"]:
                    rows = group_data.get(table, [])
                    conn = None
                    try:
                        conn = self._stats_db() if db_attr == "stats" else self._db()
                        conn.execute(f"DELETE FROM {table}")
                        if rows:
                            cols = list(rows[0].keys())
                            placeholders = ",".join("?" * len(cols))
                            col_list = ",".join(cols)
                            conn.executemany(
                                f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
                                [tuple(r.get(c) for c in cols) for r in rows],
                            )
                        conn.commit()
                        gcount += len(rows)
                    except Exception as e:
                        logger.warning(f"restore {gkey}.{table}: {e}")
                        try:
                            if conn is not None:
                                conn.rollback()
                        except Exception:
                            pass
                    finally:
                        if conn is not None:
                            try:
                                conn.close()
                            except Exception:
                                pass
                restored[gkey] = gcount
            try:
                self.ratings.clear()
                self.blacklist.clear()
                self._load_ip_blacklist()
                self._load_state()
                self._load_working_file()
                self._load_all_proxy_source_entries()
            except Exception as e:
                logger.warning(f"restore reload: {e}")
            return {"ok": True, "restored": restored}
