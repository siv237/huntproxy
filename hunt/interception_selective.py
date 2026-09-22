"""Selective transparent interception — resource registry and DNS resolution.

A "resource" is a named group of destinations (domains/subdomains/IPs). Only
the addresses of *enabled* resources are redirected into the transparent proxy;
everything else goes direct. Domain entries are resolved to IPs and re-resolved
periodically, because CDN addresses rotate.

This module holds no HuntState mixin on purpose: the mixin budget is fixed in
the architecture tests. All state lives in ``state.db`` and is reached through
the ``state`` object passed to each helper.
"""

import asyncio
import ipaddress
import json
import socket
import time
from pathlib import Path

from hunt.constants import DATA_DIR, logger

IPSET_SPEC_FILE = DATA_DIR / "interception_selective_spec.txt"

DEFAULT_CONFIG = {
    "selective_enabled": False,
    "iface": "",
    "drop_quic": True,
    "fallback_direct": True,
    "resolve_interval_sec": 300,
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interception_resources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    auto INTEGER NOT NULL DEFAULT 1,
    ports TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS interception_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT NOT NULL REFERENCES interception_resources(id) ON DELETE CASCADE,
    address TEXT NOT NULL,
    resolved TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT NOT NULL DEFAULT '',
    last_resolved_at REAL NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_interception_entries_uniq
    ON interception_entries(resource_id, address);
CREATE INDEX IF NOT EXISTS idx_interception_entries_res
    ON interception_entries(resource_id);
CREATE TABLE IF NOT EXISTS interception_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _ensure(conn):
    conn.executescript(_SCHEMA)
    cols = {row["name"] for row in conn.execute(
        "PRAGMA table_info(interception_resources)").fetchall()}
    if "auto" not in cols:
        conn.execute("ALTER TABLE interception_resources ADD COLUMN auto INTEGER NOT NULL DEFAULT 1")
    if "ports" not in cols:
        conn.execute("ALTER TABLE interception_resources ADD COLUMN ports TEXT NOT NULL DEFAULT ''")
    conn.commit()


def _iter_v4(addresses):
    out = []
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if ip.version == 4:
            out.append(str(ip))
    return out


def normalize_address(raw):
    """Normalize a destination: strip scheme/path/port, lower-case.

    ``*.example.com`` keeps its wildcard marker (resolution uses the apex);
    plain IPs and domains pass through.
    """
    if not isinstance(raw, str):
        return ""
    a = raw.strip().lower()
    if not a:
        return ""
    a = a.replace("http://", "").replace("https://", "")
    a = a.split("/", 1)[0].split("?", 1)[0]
    if "@" in a:
        a = a.rsplit("@", 1)[1]
    if a.startswith("*."):
        return "*." + a[2:].strip(".")
    if a.startswith("."):
        a = a[1:]
    if ":" in a and not a.startswith("["):
        a = a.split(":", 1)[0]
    return a.strip(".")


def resolve_sync(address):
    """Resolve one entry to IPv4 addresses. Returns ``(ips, status, error)``."""
    host = address[2:] if address.startswith("*.") else address
    if not host:
        return [], "error", "empty address"
    try:
        ip = ipaddress.ip_address(host)
        if ip.version != 4:
            return [], "error", "IPv6 is not supported by iptables"
        return [str(ip)], "ok", ""
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return [], "error", str(exc)
    ips = _iter_v4(sorted({i[4][0] for i in infos}))
    if not ips:
        return [], "error", "no IPv4 records"
    return ips, "ok", ""


def _config_get(conn, key, default):
    row = conn.execute("SELECT value FROM interception_config WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return default


def _config_set(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO interception_config (key, value) VALUES (?,?)",
        (key, json.dumps(value)),
    )


def get_config(state):
    cfg = dict(DEFAULT_CONFIG)
    try:
        conn = state._db()
        _ensure(conn)
        for key in DEFAULT_CONFIG:
            cfg[key] = _config_get(conn, key, cfg[key])
        conn.close()
    except Exception:
        logger.debug("interception config read failed", exc_info=True)
    return cfg


def _sanitize_ports(raw):
    ports = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            p = int(part)
        except ValueError:
            continue
        if 1 <= p <= 65535 and p not in ports:
            ports.append(p)
    return ",".join(str(p) for p in ports)


def _sanitize_iface(raw):
    name = str(raw or "").strip()
    if not name:
        return ""
    if len(name) > 32 or not all(c.isalnum() or c in "_.:-" for c in name):
        return ""
    return name


def set_config(state, data):
    cfg = get_config(state)
    if "selective_enabled" in data:
        cfg["selective_enabled"] = bool(data["selective_enabled"])
    if "iface" in data:
        cfg["iface"] = _sanitize_iface(data["iface"])
    if "drop_quic" in data:
        cfg["drop_quic"] = bool(data["drop_quic"])
    if "fallback_direct" in data:
        cfg["fallback_direct"] = bool(data["fallback_direct"])
    if "resolve_interval_sec" in data:
        try:
            cfg["resolve_interval_sec"] = max(30, min(86400, int(data["resolve_interval_sec"])))
        except (ValueError, TypeError):
            pass
    try:
        conn = state._db()
        _ensure(conn)
        for key, value in cfg.items():
            _config_set(conn, key, value)
        conn.commit()
        conn.close()
    except Exception:
        logger.error("interception config write failed", exc_info=True)
    return cfg


def _entry_dict(row):
    try:
        ips = json.loads(row["resolved"] or "[]")
    except (ValueError, TypeError):
        ips = []
    return {
        "id": row["id"],
        "address": row["address"],
        "ips": ips if isinstance(ips, list) else [],
        "status": row["status"],
        "error": row["error"],
        "last_resolved_at": row["last_resolved_at"],
    }


def list_resources(state):
    try:
        conn = state._db()
        _ensure(conn)
        rows = conn.execute(
            "SELECT id, name, enabled, auto, ports, created_at, updated_at "
            "FROM interception_resources ORDER BY created_at ASC"
        ).fetchall()
        resources = [dict(r) for r in rows]
        for res in resources:
            res["enabled"] = bool(res["enabled"])
            res["auto"] = bool(res["auto"])
            res["port_list"] = [int(p) for p in str(res["ports"]).split(",") if p.strip().isdigit()]
            entries = conn.execute(
                "SELECT id, address, resolved, status, error, last_resolved_at "
                "FROM interception_entries WHERE resource_id=? ORDER BY id",
                (res["id"],),
            ).fetchall()
            res["entries"] = [_entry_dict(e) for e in entries]
            res["ips"] = sorted({ip for e in res["entries"] for ip in e["ips"]})
        conn.close()
        return resources
    except Exception:
        logger.error("list_resources failed", exc_info=True)
        return []


def get_resource(state, rid):
    for res in list_resources(state):
        if res["id"] == rid:
            return res
    return None


def _save_entries(conn, rid, addresses):
    conn.execute("DELETE FROM interception_entries WHERE resource_id=?", (rid,))
    for raw in addresses or []:
        address = normalize_address(raw)
        if address:
            conn.execute(
                "INSERT OR IGNORE INTO interception_entries (resource_id, address) VALUES (?,?)",
                (rid, address),
            )


def _policy_from_data(data, auto_default, ports_default):
    auto = bool(data.get("auto", auto_default))
    ports = "" if auto else _sanitize_ports(data.get("ports", ports_default))
    return auto, ports


def create_resource(state, data):
    name = str(data.get("name", "")).strip()
    if not name:
        return None
    rid = "res_" + str(int(time.time() * 1000))
    now = time.time()
    auto, ports = _policy_from_data(data, True, "")
    try:
        conn = state._db()
        _ensure(conn)
        conn.execute(
            "INSERT INTO interception_resources (id, name, enabled, auto, ports, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, name, 1 if data.get("enabled", True) else 0,
             1 if auto else 0, ports, now, now),
        )
        _save_entries(conn, rid, data.get("addresses", []))
        conn.commit()
        conn.close()
        state._emit(f"Interception resource created: {name}", "info")
        return get_resource(state, rid)
    except Exception:
        logger.error("create_resource failed", exc_info=True)
        return None


def update_resource(state, rid, data):
    now = time.time()
    try:
        conn = state._db()
        _ensure(conn)
        row = conn.execute(
            "SELECT name, enabled, auto, ports FROM interception_resources WHERE id=?", (rid,)
        ).fetchone()
        if not row:
            conn.close()
            return None
        name = str(data.get("name", row["name"])).strip() or row["name"]
        enabled = row["enabled"] if "enabled" not in data else (1 if data["enabled"] else 0)
        auto, ports = _policy_from_data(data, bool(row["auto"]), row["ports"])
        conn.execute(
            "UPDATE interception_resources SET name=?, enabled=?, auto=?, ports=?, updated_at=? WHERE id=?",
            (name, enabled, 1 if auto else 0, ports, now, rid),
        )
        if "addresses" in data:
            _save_entries(conn, rid, data["addresses"])
        conn.commit()
        conn.close()
        state._emit(f"Interception resource updated: {name}", "info")
        return get_resource(state, rid)
    except Exception:
        logger.error("update_resource failed", exc_info=True)
        return None


def delete_resource(state, rid):
    try:
        conn = state._db()
        _ensure(conn)
        conn.execute("DELETE FROM interception_entries WHERE resource_id=?", (rid,))
        cur = conn.execute("DELETE FROM interception_resources WHERE id=?", (rid,))
        conn.commit()
        conn.close()
        if cur.rowcount:
            state._emit(f"Interception resource deleted: {rid}", "warn")
            return True
        return False
    except Exception:
        logger.error("delete_resource failed", exc_info=True)
        return False


def toggle_resource(state, rid):
    try:
        conn = state._db()
        _ensure(conn)
        row = conn.execute(
            "SELECT enabled FROM interception_resources WHERE id=?", (rid,)
        ).fetchone()
        if not row:
            conn.close()
            return None
        value = 0 if row["enabled"] else 1
        conn.execute(
            "UPDATE interception_resources SET enabled=?, updated_at=? WHERE id=?",
            (value, time.time(), rid),
        )
        conn.commit()
        conn.close()
        return get_resource(state, rid)
    except Exception:
        logger.error("toggle_resource failed", exc_info=True)
        return None


async def resolve_resource(state, rid):
    """Re-resolve every entry of one resource (DNS is offloaded to a thread)."""
    resource = get_resource(state, rid)
    if not resource:
        return None
    loop = asyncio.get_running_loop()
    now = time.time()
    try:
        conn = state._db()
        _ensure(conn)
        for entry in resource["entries"]:
            try:
                ips, status, error = await asyncio.wait_for(
                    loop.run_in_executor(None, resolve_sync, entry["address"]),
                    timeout=10,
                )
            except asyncio.TimeoutError:
                ips, status, error = [], "error", "DNS timeout"
            conn.execute(
                "UPDATE interception_entries SET resolved=?, status=?, error=?, last_resolved_at=? "
                "WHERE id=?",
                (json.dumps(ips), status, error, now, entry["id"]),
            )
        conn.commit()
        conn.close()
    except Exception:
        logger.error("resolve_resource failed", exc_info=True)
    state._emit(f"Interception resource resolved: {resource['name']}", "info")
    return get_resource(state, rid)


async def resolve_all_enabled(state):
    for res in list_resources(state):
        if res["enabled"]:
            await resolve_resource(state, res["id"])


def active_addresses(state):
    """Union of resolved IPv4 addresses across *enabled* resources."""
    ips = set()
    for res in list_resources(state):
        if res["enabled"]:
            ips.update(ip for ip in res["ips"] if ip)
    return sorted(ips)


def auto_addresses(state):
    """Resolved IPv4 addresses of enabled resources in *auto* mode.

    The transparent runner peeks/auto-detects transport only for these; manual
    resources with explicit ports use plain CONNECT.
    """
    ips = set()
    for res in list_resources(state):
        if res["enabled"] and res["auto"]:
            ips.update(ip for ip in res["ips"] if ip)
    return sorted(ips)


def write_ipset_spec(state, path=None):
    """Write the per-policy redirect spec.

    Each line is ``auto <ip>`` (redirect all TCP) or ``<port> <ip>`` (manual,
    redirect only that port). Returns the number of rules written.
    """
    path = Path(path or IPSET_SPEC_FILE)
    lines = []
    for res in list_resources(state):
        if not res["enabled"]:
            continue
        ips = [ip for ip in res["ips"] if ip]
        if res["auto"]:
            for ip in ips:
                lines.append(f"auto\t{ip}")
        else:
            for port in res["port_list"]:
                for ip in ips:
                    lines.append(f"{port}\t{ip}")
    try:
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    except Exception:
        logger.debug("write_ipset_spec failed", exc_info=True)
        return 0
    return len(lines)
