"""Interception handlers — whole-machine transparent redirect control.

The backend (when running as root, e.g. the systemd service) can *execute*
``setup_iptables.sh`` itself, so the UI offers a one-click enable/disable
toggle instead of copy-pasting ``sudo``. Connectivity is probed after
enabling and rolled back automatically on failure so the machine never
loses network access.
"""

import asyncio
import json
import logging
import os
import shutil
import socket
import struct
import fcntl
from pathlib import Path
from urllib.parse import unquote

from hunt.constants import DATA_DIR, PROJECT_DIR
from hunt.handlers import _qs, _int_param

logger = logging.getLogger(__name__)

# State file written by setup_iptables.sh after start/stop (read by the web
# backend so it can show interception status without any root privileges).
INTERCEPTION_STATE_FILE = DATA_DIR / "transparent_state.json"


def _detect_local_ips():
    """Enumerate non-loopback IPv4 addresses without root (ioctl SIOCGIFADDR)."""
    SIOCGIFADDR = 0x8915
    ips = []
    try:
        with open("/proc/net/dev") as f:
            ifaces = [ln.split(":", 1)[0].strip() for ln in f.readlines()[2:] if ":" in ln]
    except Exception:
        logger.debug("suppressed", exc_info=True)
        ifaces = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for iface in ifaces:
            try:
                ifr = iface.encode() + b"\x00" * 24
                res = fcntl.ioctl(s.fileno(), SIOCGIFADDR, ifr)
                ip = socket.inet_ntoa(res[20:24])
                if ip != "127.0.0.1":
                    ips.append(ip)
            except Exception:
                logger.debug("suppressed", exc_info=True)
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return sorted(set(ips))


def _read_interception_state():
    try:
        if INTERCEPTION_STATE_FILE.exists():
            data = json.loads(INTERCEPTION_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        logger.debug("suppressed", exc_info=True)
    return {"active": False}


class InterceptionHandlers:
    def __init__(self, state, server=None):
        self.state = state
        self.server = server

    async def _interception_readiness(self):
        """Capability + system-readiness check for one-click interception.

        Returns a dict the UI renders as a checklist. ``can_apply`` means the
        server may *execute* iptables itself (running as root). ``ready`` means
        it is safe to flip the switch right now without breaking connectivity:
        the transparent proxy is up and actually listening on its port, so
        redirected traffic has somewhere to go.
        """
        is_root = os.geteuid() == 0
        iptables_bin = shutil.which("iptables-legacy") or shutil.which("iptables")
        cgroup_v2 = Path("/sys/fs/cgroup/cgroup.controllers").exists()
        script = PROJECT_DIR / "setup_iptables.sh"
        script_present = script.exists() and os.access(script, os.X_OK)

        transparent_running = bool(
            getattr(self.server.transparent, "running", False)
            or getattr(self.state, "_transparent_running", False)
        )
        transparent_port = (
            getattr(self.server.transparent, "port", None)
            or getattr(self.state, "_transparent_port", None)
            or 17477
        )
        transparent_listening = False
        if transparent_running:
            try:
                rd, wr = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", int(transparent_port)),
                    timeout=1.0,
                )
                wr.close()
                transparent_listening = True
            except Exception:
                logger.debug("suppressed", exc_info=True)

        can_apply = bool(is_root and iptables_bin and cgroup_v2 and script_present)
        ready = bool(can_apply and transparent_running and transparent_listening)

        blockers = []
        if not is_root:
            blockers.append("backend is not running as root (no iptables rights)")
        if not iptables_bin:
            blockers.append("iptables binary not found")
        if not cgroup_v2:
            blockers.append("cgroup v2 not available (needed for --exclude-cgroup)")
        if not script_present:
            blockers.append("setup_iptables.sh not found/executable")
        if can_apply and not transparent_running:
            blockers.append("transparent proxy is not started")
        if can_apply and transparent_running and not transparent_listening:
            blockers.append(f"transparent proxy port {transparent_port} not listening")

        return {
            "is_root": is_root,
            "iptables": bool(iptables_bin),
            "cgroup_v2": cgroup_v2,
            "script_present": script_present,
            "transparent_running": transparent_running,
            "transparent_port": int(transparent_port),
            "transparent_listening": transparent_listening,
            "can_apply": can_apply,
            "ready": ready,
            "blockers": blockers,
        }

    async def _run_setup_iptables(self, args):
        """Execute setup_iptables.sh (server is root, so no sudo needed)."""
        script = str(PROJECT_DIR / "setup_iptables.sh")
        try:
            proc = await asyncio.create_subprocess_exec(
                script, *[str(a) for a in args],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        except Exception:
            logger.debug("suppressed", exc_info=True)
            return False, "failed to run setup_iptables.sh"
        output = (out or b"") + (err or b"")
        return proc.returncode == 0, output.decode(errors="replace")

    async def _interception_probe(self):
        """Best-effort egress probe: after redirect, can we still reach the net?

        Tries a few reliable hosts; if any TCP connect succeeds the machine
        still has connectivity through the transparent proxy. Used to roll
        back automatically if enabling interception would break the network.
        """
        for host, port in (("8.8.8.8", 53), ("1.1.1.1", 443)):
            try:
                rd, wr = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=5
                )
                wr.close()
                return True
            except Exception:
                logger.debug("suppressed", exc_info=True)
        return False

    async def _handle_interception(self, raw_path, body):
        """Whole-machine transparent interception status + admin command.

        When the backend runs as root (systemd service) it can *execute* the
        redirect itself — the UI then offers a one-click enable/disable toggle
        instead of copy-pasting ``sudo``. The command excludes the proxy's own
        upstream connections by **cgroup v2** (``-m cgroup --path``), the modern
        replacement for the removed ``--pid-owner``. Local/reserved
        destinations are returned by the script itself.
        """
        own_ips = _detect_local_ips()
        uid = os.getuid()
        pid = os.getpid()
        readiness = await self._interception_readiness()
        redirect_port = readiness["transparent_port"]
        apply_cmd = (
            f"sudo ./setup_iptables.sh start --redirect-port {redirect_port} "
            f"--exclude-cgroup huntproxy --cgroup-pid {pid}"
        )
        revert_cmd = "sudo ./setup_iptables.sh stop"
        return json.dumps({
            "own_ips": own_ips,
            "proxy_pid": pid,
            "proxy_uid": uid,
            "apply_command": apply_cmd,
            "revert_command": revert_cmd,
            "readiness": readiness,
            "status": _read_interception_state(),
        }), 200, "application/json"

    async def _handle_interception_apply(self, raw_path, body):
        """Enable whole-machine redirection under server control.

        Hard gate: only if the system is *ready* (root, iptables, cgroup v2,
        transparent proxy up and listening). After applying, a connectivity
        probe runs — on failure the rules are rolled back so the machine never
        loses connectivity.
        """
        readiness = await self._interception_readiness()
        if not readiness["ready"]:
            return json.dumps({
                "ok": False,
                "error": "system not ready for interception",
                "readiness": readiness,
            }), 409, "application/json"
        port = readiness["transparent_port"]
        pid = os.getpid()
        ok, output = await self._run_setup_iptables([
            "start", "--redirect-port", port,
            "--exclude-cgroup", "huntproxy", "--cgroup-pid", pid,
        ])
        if not ok:
            return json.dumps({
                "ok": False,
                "error": "setup_iptables.sh failed",
                "output": output,
            }), 500, "application/json"
        # Safety: never leave the machine without connectivity.
        if not await self._interception_probe():
            await self._run_setup_iptables(["stop"])
            return json.dumps({
                "ok": False,
                "error": "connectivity lost after enabling — rules rolled back",
            }), 500, "application/json"
        return json.dumps({
            "ok": True,
            "readiness": readiness,
            "status": _read_interception_state(),
        }), 200, "application/json"

    async def _handle_interception_stop(self, raw_path, body):
        """Disable whole-machine redirection (removes iptables rules)."""
        ok, output = await self._run_setup_iptables(["stop"])
        return json.dumps({
            "ok": ok,
            "output": output,
            "status": _read_interception_state(),
        }), 200, "application/json"
