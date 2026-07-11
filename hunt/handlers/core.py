"""Core handlers — static assets, pages, snapshot/events, dashboard, settings."""

import asyncio
import json
import logging
import subprocess
import yaml
from urllib.parse import unquote

from hunt.constants import CONFIG_PATH, WEB_DIR, PROJECT_DIR
from hunt.handlers import _qs, _int_param
from hunt.web_legacy import WEB_HTML

logger = logging.getLogger(__name__)


def _git(*args):
    """Run a git command in the project repo; return stripped stdout or ''."""
    try:
        out = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), *args],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return ""


def _commit_url(commit, remote):
    if not remote or not commit:
        return ""
    r = remote
    if r.startswith("git@"):
        r = "https://" + r[4:].replace(":", "/", 1)
    r = r.replace(".git", "")
    return f"{r}/commit/{commit}"



class CoreHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _handle_static(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        static = self.server._serve_static(path)
        if static:
            return static
        return json.dumps({"error": "not found"}), 404, "application/json"

    async def _handle_legacy(self, raw_path, body):
        return WEB_HTML, 200, "text/html; charset=utf-8"

    async def _handle_favicon(self, raw_path, body):
        return self.server._serve_static("assets/favicon.ico")

    async def _handle_index(self, raw_path, body):
        if WEB_DIR.exists() and (WEB_DIR / "index.html").exists():
            return self.server._serve_static("index.html")
        return WEB_HTML, 200, "text/html; charset=utf-8"

    async def _handle_snapshot(self, raw_path, body):
        return json.dumps(self.state.get_snapshot()), 200, "application/json"

    async def _handle_events(self, raw_path, body):
        qs = _qs(raw_path)
        since = _int_param(qs, "since", 0)
        events = self.state.events
        new = [e for e in events if e["seq"] > since]
        if not new:
            # short wait for new events
            try:
                async with self.state._cond:
                    await asyncio.wait_for(self.state._cond.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            new = [e for e in self.state.events if e["seq"] > since]
        return json.dumps(new), 200, "application/json"

    async def _handle_countries(self, raw_path, body):
        return json.dumps(self.state.get_countries()), 200, "application/json"

    async def _handle_system(self, raw_path, body):
        return json.dumps(self.state._get_system()), 200, "application/json"

    async def _handle_activity(self, raw_path, body):
        qs = _qs(raw_path)
        limit = _int_param(qs, "limit", 10)
        return json.dumps(self.state.get_activity(limit)), 200, "application/json"

    async def _handle_actions(self, raw_path, body):
        qs = _qs(raw_path)
        limit = _int_param(qs, "limit", 100)
        return json.dumps(self.state.get_actions(limit)), 200, "application/json"

    async def _handle_history(self, raw_path, body):
        qs = _qs(raw_path)
        last = qs.get("last", "1h")
        return json.dumps(self.state.get_history(last)), 200, "application/json"

    async def _handle_logs(self, raw_path, body):
        qs = _qs(raw_path)
        limit = _int_param(qs, "limit", 200)
        event_type = qs.get("type", "")
        events = self.state.get_events(limit, event_type or None)
        return json.dumps({"events": events}), 200, "application/json"

    async def _handle_settings_get(self, raw_path, body):
        if not CONFIG_PATH.exists():
            return json.dumps({"error": "config not found"}), 404, "application/json"
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)
        return json.dumps(cfg or {}), 200, "application/json"

    async def _handle_settings_post(self, raw_path, body):
        try:
            data = json.loads(body or b"{}")
            with open(CONFIG_PATH, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            self.state._emit("Settings updated", "info")
            return json.dumps({"ok": True}), 200, "application/json"
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)}), 400, "application/json"

    async def _handle_downloads_count(self, raw_path, body):
        counts = self.state.get_download_counts()
        return json.dumps(counts), 200, "application/json"

    async def _handle_version(self, raw_path, body):
        commit = _git("rev-parse", "--short", "HEAD") or "unknown"
        date = _git("show", "-s", "--format=%cs", "HEAD")
        remote = _git("remote", "get-url", "origin")
        url = _commit_url(commit, remote)
        display = f"{date} ({commit})" if date else commit
        return json.dumps({
            "commit": commit,
            "date": date,
            "url": url,
            "display": display,
        }), 200, "application/json"

    async def _handle_download(self, raw_path, body):
        path = raw_path.split("?", 1)[0]
        filename = path[len("/api/download/"):]
        filename = unquote(filename)
        allowed = ("working.txt", "blacklist.txt", "ip_blacklist.txt", "ratings.json", "config.yaml")
        if filename not in allowed:
            return json.dumps({"error": "forbidden"}), 403, "application/json"
        try:
            data = self.state.generate_download(filename)
        except FileNotFoundError:
            return json.dumps({"error": "not found"}), 404, "application/json"
        except Exception as e:
            return json.dumps({"error": str(e)}), 500, "application/json"
        ct = "application/octet-stream"
        if filename.endswith(".txt"):
            ct = "text/plain; charset=utf-8"
        elif filename.endswith(".json"):
            ct = "application/json"
        elif filename.endswith(".yaml"):
            ct = "text/yaml"
        return data, 200, ct
