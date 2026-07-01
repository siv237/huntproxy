"""Hunt control handlers — start/stop/pause/resume/skip, health, clear/export/import."""

import asyncio
import json
import time

from hunt.models import ProxyRating


class HuntHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _handle_hunt_start(self, raw_path, body):
        ok = self.state.start_hunt()
        self.state._log_action("hunt.start", "ok" if ok else "already-running")
        return json.dumps({"ok": ok, "error": None if ok else "already running"}), 200, "application/json"

    async def _handle_hunt_stop(self, raw_path, body):
        self.state._log_action("hunt.stop")
        self.state.stop_hunt()
        return json.dumps({"ok": True}), 200, "application/json"

    async def _handle_hunt_pause(self, raw_path, body):
        ok = self.state.pause_hunt(manual=True)
        self.state._log_action("hunt.pause", "ok" if ok else "not-running")
        return json.dumps({"ok": ok, "error": None if ok else "not running or already paused"}), 200, "application/json"

    async def _handle_hunt_resume(self, raw_path, body):
        ok = self.state.resume_hunt(manual=True)
        self.state._log_action("hunt.resume", "ok" if ok else "not-paused")
        return json.dumps({"ok": ok, "error": None if ok else "not paused or manual pause requires manual resume"}), 200, "application/json"

    async def _handle_hunt_skip(self, raw_path, body):
        ok = self.state.skip_phase()
        self.state._log_action("hunt.skip", "ok" if ok else "not-skippable")
        return json.dumps({"ok": ok, "error": None if ok else "nothing to skip right now"}), 200, "application/json"

    async def _handle_clear_dead(self, raw_path, body):
        dead_addrs = [a for a, r in self.state.ratings.items()
                      if r.last_status == "failed" and not r.is_favorite and not r.in_grace]
        for a in dead_addrs:
            del self.state.ratings[a]
        self.state._emit(f"Cleared {len(dead_addrs)} dead proxies", "warn")
        self.state._save_state()
        self.state._save_working_file()
        self.state._log_action("clear_dead", f"{len(dead_addrs)} proxies")
        return json.dumps({"ok": True, "cleared": len(dead_addrs)}), 200, "application/json"

    async def _handle_export(self, raw_path, body):
        alive = [r for r in self.state.ratings.values()
                 if (r.last_status == "ok" or r.in_grace) and not r.in_blacklist]
        alive.sort(key=lambda r: r.score, reverse=True)
        data = "\n".join(f"{r.address}  {r.country}  {r.last_latency:.3f}" for r in alive)
        return json.dumps({"ok": True, "data": data}), 200, "application/json"

    async def _handle_import(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
            lines = data.get("proxies", [])
            mark_favorite = bool(data.get("favorite", False))
            added = 0
            favorited = 0
            for line in lines:
                line = line.strip() if isinstance(line, str) else str(line).strip()
                if not line or line.startswith("#"):
                    continue
                # working.txt / export format: "address  country  latency"
                # — take only the first whitespace-separated token.
                addr = line.split()[0] if line.split() else ""
                if not addr or ":" not in addr:
                    continue
                is_new = addr not in self.state.ratings and addr not in self.state.blacklist
                if is_new:
                    self.state.ratings[addr] = ProxyRating(
                        address=addr, first_seen=time.time(),
                        last_check=time.time(), checks_total=1, checks_ok=1,
                        last_status="ok")
                    added += 1
                if mark_favorite and addr not in self.state.favorites:
                    self.state.favorite_add(addr)
                    favorited += 1
            msg = f"Imported {added} proxies"
            if mark_favorite:
                msg += f", favorited {favorited}"
            self.state._emit(msg, "info")
            self.state._save_state()
            self.state._save_working_file()
            result = {"ok": True, "added": added}
            if mark_favorite:
                result["favorited"] = favorited
            return json.dumps(result), 200, "application/json"
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

    async def _handle_health_start(self, raw_path, body):
        try:
            if self.state._health_running:
                self.state._log_action("health.start", "already-running")
                return json.dumps({"ok": False, "error": "already_running"}), 409, "application/json"
            self.state._log_action("health.start", "recheck-all")
            self.state._health_task = asyncio.create_task(self.state._health_check(manual=True))
            return json.dumps({"ok": True}), 200, "application/json"
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"

    async def _handle_health_stop(self, raw_path, body):
        try:
            if not self.state._health_running:
                return json.dumps({"ok": False, "error": "not_running"}), 409, "application/json"
            self.state._log_action("health.stop", "abort-recheck")
            self.state.stop_health()
            return json.dumps({"ok": True}), 200, "application/json"
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}), 500, "application/json"
