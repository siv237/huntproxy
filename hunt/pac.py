"""Functional split of the huntproxy backend."""

import json
import socket
import time

from hunt.constants import logger


def render_pac(config: dict) -> str:
    """Render a Proxy Auto-Config script from a config dict.

    Mirrors the PHP ``autoproxyRenderPac`` engine: DIRECT rules come first
    (direct-host masks, internal nets, plain hostnames), then the default
    ``PROXY host:port`` return (with fail-over proxies when listed).
    """
    direct_hosts = config.get("direct_hosts") or []
    internal_nets = config.get("internal_nets") or []
    proxies = config.get("proxies") or []
    if proxies:
        proxy_ret = "; ".join(f"PROXY {p['host']}:{p['port']}" for p in proxies)
    else:
        host = config.get("proxy_host", "")
        port = config.get("proxy_port", 0)
        proxy_ret = f"PROXY {host}:{port}" if host and port else "DIRECT"

    lines = []
    lines.append("function FindProxyForURL(url, host) {")
    lines.append(f"    var directHosts = {json.dumps(direct_hosts)};")
    lines.append("    for (var i = 0; i < directHosts.length; i++)")
    lines.append("        if (shExpMatch(host, directHosts[i])) return \"DIRECT\";")
    lines.append("")
    lines.append(f"    var internalNets = {json.dumps(internal_nets)};")
    lines.append("    for (var j = 0; j < internalNets.length; j++)")
    lines.append("        if (isInNet(dnsResolve(host), internalNets[j].network, internalNets[j].mask)) return \"DIRECT\";")
    lines.append("")
    lines.append("    if (isPlainHostName(host)) return \"DIRECT\";")
    lines.append("")
    lines.append(f"    return \"{proxy_ret}\";")
    lines.append("}")
    return "\n".join(lines) + "\n"


class PacMixin:
    _PAC_CACHE_TTL = 5

    def _pac_get(self, key: str, default: str = "") -> str:
        try:
            conn = self._db()
            row = conn.execute("SELECT value FROM pac_config WHERE key=?", (key,)).fetchone()
            conn.close()
            return row["value"] if row else default
        except Exception:
            return default

    def _pac_set(self, key: str, value: str):
        try:
            conn = self._db()
            conn.execute(
                "INSERT OR REPLACE INTO pac_config (key, value) VALUES (?,?)", (key, value))
            conn.commit()
            conn.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)

    def detect_lan_ip(self) -> str:
        """Resolve the local interface IP without external deps via a UDP
        connect to a public resolver (no packets are actually sent)."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip:
                return ip
        except Exception:
            logger.debug("suppressed", exc_info=True)
        finally:
            try:
                s.close()
            except Exception:
                logger.debug("suppressed", exc_info=True)
        return "127.0.0.1"

    def list_local_ips(self) -> list:
        """Enumerate all local interface IPv4 addresses (a box may have many
        besides loopback). Uses ``ip -4 -o addr`` (no psutil dependency);
        falls back to the default-route IP, then loopback."""
        ips = set()
        try:
            import subprocess
            out = subprocess.run(
                ["ip", "-4", "-o", "addr", "show"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            for line in out.splitlines():
                if " inet " not in line:
                    continue
                addr = line.split(" inet ")[1].split("/")[0].strip()
                if addr and ":" not in addr:
                    ips.add(addr)
        except Exception:
            logger.debug("suppressed", exc_info=True)
        if not ips:
            ips.add(self.detect_lan_ip())
        ips.add("127.0.0.1")
        return sorted(ips)

    def _pac_default_port(self) -> int:
        runner = getattr(self, "proxy_runner", None)
        if runner is not None:
            return getattr(runner, "port", 17277)
        return 17277

    def _pac_web_port(self) -> int:
        try:
            return int(self.config.get("hunt", {}).get("web_listen_port", 17177))
        except (AttributeError, TypeError, ValueError):
            return 17177

    def get_pac_config(self) -> dict:
        enabled = self._pac_get("enabled", "false") == "true"
        proxy_host = self._pac_get("proxy_host", "").strip()
        if not proxy_host:
            proxy_host = "127.0.0.1"
        raw_port = self._pac_get("proxy_port", "")
        try:
            proxy_port = int(raw_port) if raw_port else self._pac_default_port()
        except ValueError:
            proxy_port = self._pac_default_port()
        direct_hosts = []
        internal_nets = []
        try:
            conn = self._db()
            rows = conn.execute("SELECT pattern FROM pac_direct_hosts ORDER BY id").fetchall()
            direct_hosts = [r["pattern"] for r in rows]
            rows = conn.execute("SELECT network, mask FROM pac_internal_nets ORDER BY id").fetchall()
            internal_nets = [{"network": r["network"], "mask": r["mask"]} for r in rows]
            conn.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)
        config = {
            "enabled": enabled,
            "proxy_host": proxy_host,
            "proxy_port": proxy_port,
            "direct_hosts": direct_hosts,
            "internal_nets": internal_nets,
            "url": f"http://{proxy_host}:{self._pac_web_port()}/pac.js",
        }
        config["preview"] = self.render_pac()
        return config

    def save_pac_config(self, data: dict) -> dict:
        if "enabled" in data:
            self._pac_set("enabled", "true" if data["enabled"] else "false")
        if data.get("proxy_host") is not None:
            self._pac_set("proxy_host", str(data["proxy_host"]).strip())
        if data.get("proxy_port") is not None:
            try:
                self._pac_set("proxy_port", str(int(data["proxy_port"])))
            except (ValueError, TypeError):
                logger.debug("suppressed", exc_info=True)
        try:
            conn = self._db()
            if "direct_hosts" in data:
                conn.execute("DELETE FROM pac_direct_hosts")
                for pattern in data["direct_hosts"]:
                    p = str(pattern).strip()
                    if p:
                        conn.execute("INSERT OR IGNORE INTO pac_direct_hosts (pattern) VALUES (?)", (p,))
            if "internal_nets" in data:
                conn.execute("DELETE FROM pac_internal_nets")
                for entry in data["internal_nets"]:
                    network = str(entry.get("network", "")).strip()
                    mask = str(entry.get("mask", "")).strip()
                    if network and mask:
                        conn.execute(
                            "INSERT INTO pac_internal_nets (network, mask) VALUES (?,?)",
                            (network, mask))
            conn.commit()
            conn.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)
        self._pac_cache_invalidate()
        return self.get_pac_config()

    def _pac_cache_invalidate(self):
        self._pac_cache = None

    def _pac_cache_get(self):
        cache = getattr(self, "_pac_cache", None)
        ts = getattr(self, "_pac_cache_ts", 0)
        if cache is None or (time.time() - ts) >= self._PAC_CACHE_TTL:
            return self._pac_cache_build()
        return cache

    def _pac_cache_build(self):
        enabled = self._pac_get("enabled", "false") == "true"
        proxy_host = self._pac_get("proxy_host", "").strip() or "127.0.0.1"
        raw_port = self._pac_get("proxy_port", "")
        try:
            proxy_port = int(raw_port) if raw_port else self._pac_default_port()
        except ValueError:
            proxy_port = self._pac_default_port()
        direct_hosts = []
        internal_nets = []
        try:
            conn = self._db()
            rows = conn.execute("SELECT pattern FROM pac_direct_hosts ORDER BY id").fetchall()
            direct_hosts = [r["pattern"] for r in rows]
            rows = conn.execute("SELECT network, mask FROM pac_internal_nets ORDER BY id").fetchall()
            internal_nets = [{"network": r["network"], "mask": r["mask"]} for r in rows]
            conn.close()
        except Exception:
            logger.debug("suppressed", exc_info=True)
        config = {
            "enabled": enabled,
            "proxy_host": proxy_host,
            "proxy_port": proxy_port,
            "direct_hosts": direct_hosts,
            "internal_nets": internal_nets,
        }
        cache = {"enabled": enabled, "pac": render_pac(config)}
        self._pac_cache = cache
        self._pac_cache_ts = time.time()
        return cache

    def render_pac(self) -> str:
        return self._pac_cache_get()["pac"]
