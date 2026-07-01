"""State download/export methods — extracted from state.py."""
import json
import time

class StateDownloadMixin:
    def get_download_counts(self) -> dict:
            """Return row/entry counts for each downloadable artifact."""
            counts = {}
            try:
                conn = self._db()
                counts["working.txt"] = conn.execute("SELECT COUNT(*) FROM working_proxies").fetchone()[0]
                counts["blacklist.txt"] = conn.execute("SELECT COUNT(*) FROM blacklist").fetchone()[0]
                counts["ip_blacklist.txt"] = conn.execute("SELECT COUNT(*) FROM ip_blacklist_entries").fetchone()[0]
                counts["ratings.json"] = conn.execute("SELECT COUNT(*) FROM ratings").fetchone()[0]
                conn.close()
            except Exception as e:
                logger.warning(f"download counts: {e}")
            try:
                from hunt.constants import CONFIG_PATH
                counts["config.yaml"] = 1 if CONFIG_PATH.exists() else 0
            except Exception:
                counts["config.yaml"] = 0
            return counts

    def generate_download(self, filename: str) -> bytes:
            """Generate the requested artifact content from DB/memory."""
            if filename == "working.txt":
                return self._gen_working_txt()
            if filename == "blacklist.txt":
                return self._gen_blacklist_txt()
            if filename == "ip_blacklist.txt":
                return self._gen_ip_blacklist_txt()
            if filename == "ratings.json":
                return self._gen_ratings_json()
            if filename == "config.yaml":
                from hunt.constants import CONFIG_PATH
                if not CONFIG_PATH.exists():
                    raise FileNotFoundError("config.yaml")
                return CONFIG_PATH.read_bytes()
            raise ValueError(f"unknown download: {filename}")

    def _gen_working_txt(self) -> bytes:
            lines = ["# huntproxy alive working proxies (generated from DB)"]
            try:
                conn = self._db()
                rows = conn.execute(
                    "SELECT address, country, latency, score FROM working_proxies ORDER BY score DESC"
                ).fetchall()
                conn.close()
                for r in rows:
                    lines.append(f"{r['address']}  {r['country'] or ''}  {r['latency'] or 0:.3f}")
            except Exception as e:
                logger.warning(f"gen working.txt: {e}")
            return "\n".join(lines).encode()

    def _gen_blacklist_txt(self) -> bytes:
            lines = ["# huntproxy blacklist (operator-curated, NOT dead proxies)"]
            for addr, reason in sorted(self.blacklist.items()):
                lines.append(f"{addr}  {reason}")
            return "\n".join(lines).encode()

    def _gen_ip_blacklist_txt(self) -> bytes:
            lines = [
                "# huntproxy downloaded IP blacklist (egress IP checks)",
                f"# entries: {len(self.ip_blacklist_entries)} sources: {sum(len(m) for m in self.ip_blacklist_entries.values())}",
            ]
            for entry, metas in sorted(self.ip_blacklist_entries.items()):
                names = [m.get("source_name") or m.get("source_id") for m in metas]
                reason = ", ".join(names) if names else ""
                lines.append(f"{entry}  {reason}")
            return "\n".join(lines).encode()

    def _gen_ratings_json(self) -> bytes:
            data = {
                "proxies": [r.to_dict() for r in self.ratings.values()],
                "proxy_runner": {
                    "direct_mode": getattr(self, '_proxy_direct_mode', False),
                    "active_proxy_addr": getattr(self, '_proxy_active_addr', None),
                    "socks5_port": getattr(self, '_socks5_port', 17278),
                },
                "services": {
                    "hunt_running": getattr(self, '_hunt_running', False),
                    "proxy_running": getattr(self, '_proxy_running', False),
                    "proxy_port": getattr(self, '_proxy_port', 17277),
                    "socks5_running": getattr(self, '_socks5_running', False),
                    "socks5_port": getattr(self, '_socks5_port', 17278),
                    "transparent_running": getattr(self, '_transparent_running', False),
                    "transparent_port": getattr(self, '_transparent_port', 17477),
                },
            }
            return json.dumps(data, indent=2).encode()

