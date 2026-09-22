"""Selective interception handlers — per-resource transparent redirects.

Management only: the domain logic lives in ``hunt/interception_selective.py``.
"""

import asyncio
import json
import os
from urllib.parse import unquote

from hunt.handlers import _json_body
import hunt.interception_selective as ise
import hunt.interception_reconcile as rec


class SelectiveInterceptionHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _readiness(self):
        handler = getattr(self.server, "_h_interception", None)
        if handler is None:
            return None
        try:
            return await handler._interception_readiness()
        except Exception:
            return None

    async def _status_payload(self):
        cfg = ise.get_config(self.state)
        resources = ise.list_resources(self.state)
        try:
            actual = await rec.actual_state()
        except Exception:
            actual = {"available": False}
        desired = bool(cfg["selective_enabled"])
        applied = bool(actual.get("selective_jump"))
        st = rec.read_state_file()
        whole_active = bool(st.get("active") and st.get("mode") != "selective")
        mismatch = ""
        if applied and not desired:
            mismatch = "leftover"
        elif desired and not applied:
            mismatch = "pending"
        active = [(r["id"], r["name"]) for r in resources if r["enabled"]]
        return {
            "config": cfg,
            "resources": resources,
            "actual": actual,
            "readiness": await self._readiness(),
            "desired": desired,
            "applied": applied,
            "whole_active": whole_active,
            "mismatch": mismatch,
            "enabled_resources": len(active),
            "ip_count": len(ise.active_addresses(self.state)),
            "spec_file": str(ise.IPSET_SPEC_FILE),
        }

    async def _handle_selective_post(self, raw_path, body):
        """Dispatch POST /api/interception/selective/<action>."""
        action = raw_path.split("?", 1)[0][len("/api/interception/selective/"):].strip("/")
        handlers = {
            "config": self._handle_selective_config,
            "apply": self._handle_selective_apply,
            "stop": self._handle_selective_stop,
            "reconcile": self._handle_selective_reconcile,
        }
        handler = handlers.get(action)
        if handler is None:
            return json.dumps({"ok": False, "error": "unknown action"}), 404, "application/json"
        return await handler(raw_path, body)

    async def _handle_selective_status(self, raw_path, body):
        return json.dumps(await self._status_payload()), 200, "application/json"

    async def _handle_selective_rules(self, raw_path, body):
        try:
            lines = await rec.active_rules()
        except Exception:
            lines = []
        return json.dumps({"lines": lines}), 200, "application/json"

    async def _handle_selective_config(self, raw_path, body):
        data = _json_body(body)
        cfg = ise.set_config(self.state, data)
        return json.dumps({"ok": True, "config": cfg}), 200, "application/json"

    async def _handle_selective_apply(self, raw_path, body):
        st = rec.read_state_file()
        if st.get("active") and st.get("mode") != "selective":
            return json.dumps({
                "ok": False,
                "error": "whole-machine interception is active — disable it first",
            }), 409, "application/json"
        readiness = await self._readiness()
        if not readiness or not readiness.get("ready"):
            return json.dumps({
                "ok": False,
                "error": "system not ready for selective interception",
                "readiness": readiness,
            }), 409, "application/json"
        cfg = ise.get_config(self.state)
        count = ise.write_ipset_spec(self.state)
        if count == 0:
            # A freshly added resource may not have been resolved yet — resolve
            # now instead of failing the toggle.
            await ise.resolve_all_enabled(self.state)
            count = ise.write_ipset_spec(self.state)
        if count == 0:
            return json.dumps({
                "ok": False,
                "error": "no resolved addresses — add resources or resolve them first",
            }), 409, "application/json"
        port = readiness["transparent_port"]
        args = ["start", "--selective", "--redirect-port", port,
                "--ipset-spec", str(ise.IPSET_SPEC_FILE),
                "--exclude-cgroup", "huntproxy", "--cgroup-pid", str(os.getpid())]
        if cfg["iface"]:
            args += ["--iface", cfg["iface"]]
        if cfg["drop_quic"]:
            args += ["--drop-quic"]
        ok, output = await rec.run_setup_iptables(args)
        if not ok:
            # Clean up any partial state the script may have left behind.
            await rec.run_setup_iptables(["stop"])
            return json.dumps({
                "ok": False, "error": "setup_iptables.sh failed", "output": output,
            }), 500, "application/json"
        if not await rec.probe_connectivity():
            await rec.run_setup_iptables(["stop"])
            return json.dumps({
                "ok": False,
                "error": "connectivity lost after enabling — rules rolled back",
            }), 500, "application/json"
        ise.set_config(self.state, {"selective_enabled": True})
        self.state._log_action("interception.selective.apply", f"{count} ips")
        self.state._emit(f"Selective interception enabled ({count} addresses)", "info")
        return json.dumps({"ok": True, "ip_count": count}), 200, "application/json"

    async def _handle_selective_stop(self, raw_path, body):
        ok, output = await rec.run_setup_iptables(["stop"])
        ise.set_config(self.state, {"selective_enabled": False})
        self.state._log_action("interception.selective.stop")
        return json.dumps({"ok": ok, "output": output}), 200, "application/json"

    async def _handle_selective_reconcile(self, raw_path, body):
        result = await rec.reconcile_on_startup(self.state)
        return json.dumps({"ok": True, "reconcile": result}), 200, "application/json"

    # ── Resource CRUD ───────────────────────────────────────────────────

    async def _handle_resources_list(self, raw_path, body):
        return json.dumps({"resources": ise.list_resources(self.state)}), 200, "application/json"

    async def _handle_resource_create(self, raw_path, body):
        data = _json_body(body)
        result = ise.create_resource(self.state, data)
        if not result:
            return json.dumps({"ok": False, "error": "name is required"}), 400, "application/json"
        asyncio.create_task(ise.resolve_resource(self.state, result["id"]))
        return json.dumps({"ok": True, "resource": result}), 200, "application/json"

    async def _handle_resource_post(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        rest = path[len("/api/interception/resources/"):]
        parts = [p for p in rest.split("/") if p]
        if not parts:
            return json.dumps({"ok": False, "error": "resource id required"}), 400, "application/json"
        rid = unquote(parts[0])
        action = parts[1] if len(parts) > 1 else ""
        if action == "toggle":
            result = ise.toggle_resource(self.state, rid)
        elif action == "resolve":
            result = await ise.resolve_resource(self.state, rid)
        elif action == "":
            result = ise.update_resource(self.state, rid, _json_body(body))
            if result:
                asyncio.create_task(ise.resolve_resource(self.state, rid))
        else:
            return json.dumps({"ok": False, "error": "unknown action"}), 404, "application/json"
        if not result:
            return json.dumps({"ok": False, "error": "resource not found"}), 404, "application/json"
        return json.dumps({"ok": True, "resource": result}), 200, "application/json"

    async def _handle_resource_delete(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        rid = unquote(path[len("/api/interception/resources/"):].split("/", 1)[0])
        if ise.delete_resource(self.state, rid):
            return json.dumps({"ok": True}), 200, "application/json"
        return json.dumps({"ok": False, "error": "resource not found"}), 404, "application/json"
