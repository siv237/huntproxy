"""Functional split of the huntproxy backend."""

import json

from hunt.handlers import _json_body


class PacHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _handle_pac_get(self, raw_path, body):
        if not self.state.get_pac_config()["enabled"]:
            return json.dumps({"error": "pac disabled"}), 503, "application/json"
        return self.state.render_pac(), 200, "application/x-ns-proxy-autoconfig; charset=utf-8"

    async def _handle_pac_config_get(self, raw_path, body):
        return json.dumps(self.state.get_pac_config()), 200, "application/json"

    async def _handle_pac_config_post(self, raw_path, body):
        data = _json_body(body)
        return json.dumps(self.state.save_pac_config(data)), 200, "application/json"

    async def _handle_pac_detect_ip(self, raw_path, body):
        return json.dumps({"ip": self.state.detect_lan_ip()}), 200, "application/json"
