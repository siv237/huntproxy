"""Selective interception — kernel inspection, reconciliation and resolver loop.

Reading the real iptables/ipset state (not just the persisted config) is what
lets the UI detect that rules survived a crash while the feature is off, or
that the feature is enabled with no active rules after a restart.
"""

import asyncio
import json
import os
import shutil

from hunt.constants import DATA_DIR, PROJECT_DIR, logger
from hunt.interception_selective import get_config, resolve_all_enabled

SELECTIVE_CHAIN = "HUNTPROXY_SELECTIVE"
QUIC_CHAIN = "HUNTPROXY_SELECTIVE_QUIC"
STATE_FILE = DATA_DIR / "transparent_state.json"


def read_state_file():
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        logger.debug("read_state_file failed", exc_info=True)
    return {"active": False}


async def _run(binary, *args, timeout=5):
    try:
        proc = await asyncio.create_subprocess_exec(
            binary, *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, (out or b"").decode(errors="replace"), (err or b"").decode(errors="replace")
    except Exception:
        logger.debug("command failed: %s", binary, exc_info=True)
        return None, "", ""


async def _iptables(binary, table, *args):
    code, out, _ = await _run(binary, "-t", table, *args)
    return code == 0, out


async def actual_state():
    """Inspect the kernel: what redirect rules/ipset really exist right now."""
    ipt = shutil.which("iptables-legacy") or shutil.which("iptables")
    ipset_bin = shutil.which("ipset")
    result = {
        "available": bool(ipt),
        "root": os.geteuid() == 0,
        "all_chain": False,
        "selective_chain": False,
        "selective_jump": False,
        "quic_drop": False,
        "ipsets": [],
    }
    if not ipt:
        return result
    ok, _ = await _iptables(ipt, "nat", "-C", "OUTPUT", "-j", "HUNTPROXY_REDIRECT")
    result["all_chain"] = ok
    ok, _ = await _iptables(ipt, "nat", "-S", SELECTIVE_CHAIN)
    result["selective_chain"] = ok
    ok, _ = await _iptables(ipt, "nat", "-C", "OUTPUT", "-j", SELECTIVE_CHAIN)
    result["selective_jump"] = ok
    ok, _ = await _iptables(ipt, "filter", "-C", "OUTPUT", "-j", QUIC_CHAIN)
    result["quic_drop"] = ok
    if ipset_bin:
        code, out, _ = await _run(ipset_bin, "list", "-n")
        if code == 0:
            result["ipsets"] = [
                ln.strip() for ln in out.splitlines()
                if ln.strip().startswith(("huntproxy_sel", "huntproxy_selective"))
            ]
    return result


async def run_setup_iptables(args):
    script = str(PROJECT_DIR / "setup_iptables.sh")
    code, out, err = await _run(script, *[str(a) for a in args], timeout=30)
    if code is None:
        return False, "failed to run setup_iptables.sh"
    return code == 0, (out + err)


async def probe_connectivity():
    for host, port in (("8.8.8.8", 53), ("1.1.1.1", 443)):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=5
            )
            writer.close()
            return True
        except Exception:
            logger.debug("probe host failed: %s", host, exc_info=True)
    return False


async def reconcile_on_startup(state):
    """Compare desired state with real iptables rules after a restart.

    A leftover redirect while the feature is off is removed — with the
    transparent proxy possibly down, stale rules would silently break the
    machine's networking.
    """
    actual = await actual_state()
    desired = get_config(state)["selective_enabled"]
    file_active = bool(read_state_file().get("active"))
    applied = bool(
        actual.get("selective_jump") or actual.get("all_chain")
        or actual.get("selective_chain") or actual.get("quic_drop")
        or actual.get("ipsets")
    )
    status = {
        "available": actual.get("available", False),
        "desired": desired,
        "applied": applied,
        "leftover": applied and not (desired or file_active),
        "pending": (desired or file_active) and not applied,
        "ipsets": actual.get("ipsets", []),
    }
    if status["leftover"] and actual.get("root"):
        ok, _ = await run_setup_iptables(["stop"])
        status["cleaned"] = ok
        state._emit("Interception: leftover redirect rules removed on startup", "warn")
    elif status["pending"]:
        state._emit("Interception: enabled but no active rules — re-apply from UI", "warn")
    return status


async def resolver_loop(state):
    """Periodically re-resolve enabled resources so CDN IP drift is tracked."""
    while True:
        cfg = get_config(state)
        try:
            await resolve_all_enabled(state)
        except Exception:
            logger.debug("resolver loop iteration failed", exc_info=True)
        await asyncio.sleep(max(30, int(cfg.get("resolve_interval_sec", 300))))


def start_resolver(state):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    task = loop.create_task(resolver_loop(state))
    state._interception_resolver_task = task
    return task
