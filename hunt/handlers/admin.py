"""Admin handlers — schedules, backup/restore, canary, channel, country filter."""

import asyncio
import json
import time

from hunt.handlers import _qs, _int_param, _json_body


class AdminHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    # === Channel (engine outbound proxy) ===

    async def _handle_channel_status(self, raw_path, body):
        return json.dumps(self.state.get_channel_status()), 200, "application/json"

    async def _handle_channel_select(self, raw_path, body):
        qs = _qs(raw_path)
        route = qs.get("route", "").strip()
        self.state.set_channel(route)
        self.state._log_action("channel.select", route or "direct")
        return json.dumps(self.state.get_channel_status()), 200, "application/json"

    async def _handle_country_filter(self, raw_path, body):
        qs = _qs(raw_path)
        code = qs.get("code", "").upper()
        self.state.country_filter = code
        self.state._save_state()
        self.state._emit(f"Country filter set to: {code or 'ALL'}", "info")
        return json.dumps({"ok": True, "country_filter": self.state.country_filter}), 200, "application/json"

    # === Backup / Restore ===

    async def _handle_backup_groups(self, raw_path, body):
        return json.dumps({"groups": self.state.get_backup_groups()}), 200, "application/json"

    async def _handle_backup(self, raw_path, body):
        try:
            payload = _json_body(body)
            groups = payload.get("groups", [])
            if not groups:
                return json.dumps({"error": "no groups selected"}), 400, "application/json"
            data = self.state.create_backup(groups)
            self.state._log_action("backup", f"groups: {','.join(groups)}")
            ts = time.strftime("%Y%m%d_%H%M%S")
            return data, 200, "application/json"
        except Exception as e:
            return json.dumps({"error": str(e)}), 500, "application/json"

    async def _handle_restore(self, raw_path, body):
        try:
            payload = _json_body(body)
            groups = payload.get("groups", [])
            backup_data = payload.get("data", "")
            if not groups:
                return json.dumps({"error": "no groups selected"}), 400, "application/json"
            if not backup_data:
                return json.dumps({"error": "no backup data"}), 400, "application/json"
            result = self.state.restore_backup(
                backup_data.encode() if isinstance(backup_data, str) else backup_data,
                groups,
            )
            if result.get("ok"):
                self.state._log_action("restore", f"groups: {','.join(groups)}")
            return json.dumps(result), 200 if result.get("ok") else 400, "application/json"
        except Exception as e:
            return json.dumps({"error": str(e)}), 500, "application/json"

    # === Scheduler ===

    async def _handle_schedules_list(self, raw_path, body):
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"schedules": [], "status": {"running": False, "paused": False, "running_tasks": [], "queued": []}}), 200, "application/json"
        return json.dumps({"schedules": sched.list_schedules(), "status": sched.get_status()}), 200, "application/json"

    async def _handle_schedule_create(self, raw_path, body):
        data = _json_body(body)
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
        try:
            result = await sched.add_schedule(
                sid=data.get("id", ""),
                name=data.get("name", ""),
                task_type=data.get("task_type", ""),
                interval_sec=int(data.get("interval_sec", 3600)),
                config=data.get("config", {}),
                enabled=data.get("enabled", True),
            )
            self.state._log_action("schedule.add", data.get("id", ""))
            return json.dumps({"ok": True, "schedule": result}), 200, "application/json"
        except ValueError as e:
            return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

    async def _handle_schedules_status(self, raw_path, body):
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"running": False, "paused": False, "running_tasks": [], "queued": []}), 200, "application/json"
        return json.dumps(sched.get_status()), 200, "application/json"

    async def _handle_schedules_log(self, raw_path, body):
        qs = _qs(raw_path)
        limit = _int_param(qs, "limit", 50)
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"entries": []}), 200, "application/json"
        return json.dumps({"entries": sched.get_log(limit)}), 200, "application/json"

    async def _handle_schedules_pause(self, raw_path, body):
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
        sched.pause_all()
        self.state._log_action("schedule.pause_all")
        return json.dumps({"ok": True, "paused": True}), 200, "application/json"

    async def _handle_schedules_resume(self, raw_path, body):
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
        sched.resume_all()
        self.state._log_action("schedule.resume_all")
        return json.dumps({"ok": True, "paused": False}), 200, "application/json"

    async def _handle_schedules_restore_defaults(self, raw_path, body):
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
        added = await sched.restore_defaults()
        self.state._log_action("schedule.restore_defaults", ", ".join(added) or "none")
        return json.dumps({"ok": True, "added": added, "schedules": sched.list_schedules()}), 200, "application/json"

    async def _handle_schedule_post_subpath(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        if path.endswith("/toggle"):
            sid = path[len("/api/schedules/"):-len("/toggle")]
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            result = await sched.toggle_schedule(sid)
            if result is None:
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            self.state._log_action("schedule.toggle", sid)
            return json.dumps({"ok": True, "enabled": result["enabled"]}), 200, "application/json"
        if path.endswith("/run"):
            sid = path[len("/api/schedules/"):-len("/run")]
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            ok = await sched.trigger_now(sid)
            if not ok:
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            self.state._log_action("schedule.run_now", sid)
            return json.dumps({"ok": True}), 200, "application/json"
        if path.endswith("/stop"):
            sid = path[len("/api/schedules/"):-len("/stop")]
            sched = getattr(self.state, "scheduler", None)
            if sched is None:
                return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
            ok = await sched.cancel_running(sid)
            if not ok:
                return json.dumps({"ok": False, "error": "not running"}), 404, "application/json"
            self.state._log_action("schedule.stop", sid)
            return json.dumps({"ok": True}), 200, "application/json"
        sid = path[len("/api/schedules/"):]
        data = _json_body(body)
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
        try:
            result = await sched.update_schedule(sid, **data)
            if result is None:
                return json.dumps({"ok": False, "error": "not found"}), 404, "application/json"
            self.state._log_action("schedule.update", sid)
            return json.dumps({"ok": True, "schedule": result}), 200, "application/json"
        except ValueError as e:
            return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

    async def _handle_schedule_delete(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        sid = path[len("/api/schedules/"):]
        sched = getattr(self.state, "scheduler", None)
        if sched is None:
            return json.dumps({"ok": False, "error": "scheduler not initialized"}), 500, "application/json"
        ok = await sched.delete_schedule(sid)
        if ok:
            self.state._log_action("schedule.delete", sid)
        return json.dumps({"ok": ok}), 200, "application/json"

    # === Canary / Internet Connectivity ===

    async def _handle_canary_status(self, raw_path, body):
        result = self.state.get_canary_status()
        asyncio.ensure_future(self.state._check_canary())
        return json.dumps(result), 200, "application/json"

    async def _handle_canary_history(self, raw_path, body):
        qs = _qs(raw_path)
        hours = _int_param(qs, "hours", 24)
        result = self.state.get_canary_history(hours)
        return json.dumps(result), 200, "application/json"

    async def _handle_canary_hosts(self, raw_path, body):
        data = _json_body(body)
        hosts = data.get("canary_hosts", [])
        if hosts:
            self.state.set_canary_hosts(hosts)
        return json.dumps({"ok": True, "canary_hosts": self.state.canary_hosts}), 200, "application/json"
