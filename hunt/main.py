"""Functional split of the huntproxy backend."""

import argparse
import asyncio
import resource
import signal
import yaml
from hunt.constants import CONFIG_PATH, DATA_DIR
from hunt.logging_config import setup_logging
from hunt.scheduler import SchedulerEngine
from hunt.server import HuntServer
from hunt.state import HuntState
import logging

logger = logging.getLogger(__name__)

async def amain(config: dict):
    hunt_cfg = config.get("hunt", {})
    host = hunt_cfg.get("web_listen_host", "127.0.0.1")
    port = hunt_cfg.get("web_listen_port", 17177)

    state = HuntState(config)
    server = HuntServer(state, host, port)
    state.proxy_runner = server.proxy

    # Start the web UI immediately so scheduler progress is visible.
    server_task = asyncio.create_task(server.start())

    # Restore proxy/SOCKS services that were running before restart.
    restored = []
    if getattr(state, '_proxy_running', False):
        proxy_port = getattr(state, '_proxy_port', 17277)
        await server.proxy.start(proxy_port)
        restored.append(f"proxy:{proxy_port}")
    if getattr(state, '_socks5_running', False):
        socks5_port = getattr(state, '_socks5_port', 17278)
        await server.socks5.start(socks5_port)
        restored.append(f"socks5:{socks5_port}")
    if getattr(state, '_transparent_running', False):
        transparent_port = getattr(state, '_transparent_port', 17477)
        await server.transparent.start(transparent_port)
        restored.append(f"transparent:{transparent_port}")
    if getattr(state, '_proxy_direct_mode', False):
        server.proxy.direct_mode = True
    if getattr(state, '_proxy_active_addr', None):
        server.proxy.select(state._proxy_active_addr, record=False)
    if restored:
        state._emit(f"Restored services after restart: {', '.join(restored)}", "info")

    print("=" * 56)
    print(f"  huntproxy HUNT — web UI: http://{host}:{port}/")
    print(f"  data dir: {DATA_DIR}")
    print("  Ctrl+C to stop")
    print("=" * 56)

    # Start the unified scheduler. It drives ALL periodic maintenance
    # (health_check, proxy_check, IP blacklist / blocklist refresh, history)
    # based on each schedule's real last_ok completion time, so after a cold
    # restart every due task launches immediately — no special startup cycle
    # is needed. A leftover _hunt_running flag (e.g. from a previous crashed
    # run) is cleared by the scheduler's stale-flag guard, so proxy_check is
    # never blocked forever after a restart.
    scheduler = SchedulerEngine(state)
    state.scheduler = scheduler
    await scheduler.prepare()
    await scheduler.start_loop()

    async def shutdown():
        await scheduler.stop()
        server_task.cancel()
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        except Exception:
            logger.debug("suppressed", exc_info=True)

    try:
        await server_task
    except asyncio.CancelledError:
        pass
    finally:
        # Preserve running-service flags so they are restored after restart.
        # server.stop() sets _proxy_running/_socks5_running to False internally,
        # so we capture the pre-shutdown state and re-save it after stopping.
        _saved_flags = {
            '_hunt_running': getattr(state, '_hunt_running', False),
            '_proxy_running': getattr(state, '_proxy_running', False),
            '_proxy_port': getattr(state, '_proxy_port', 17277),
            '_socks5_running': getattr(state, '_socks5_running', False),
            '_socks5_port': getattr(state, '_socks5_port', 17278),
            '_transparent_running': getattr(state, '_transparent_running', False),
            '_transparent_port': getattr(state, '_transparent_port', 17477),
            '_proxy_active_addr': getattr(state, '_proxy_active_addr', None),
            '_proxy_direct_mode': getattr(state, '_proxy_direct_mode', False),
        }
        await server.stop()
        for k, v in _saved_flags.items():
            setattr(state, k, v)
        state._save_state()
        state._save_working_file()

def main():
    setup_logging()

    # Raise the file-descriptor limit so parallel proxy checks (300+)
    # through a channel don't hit EMFILE.  Best-effort: ignore if no
    # permission (already raised by the launch script or OS policy).
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < 65535:
            resource.setrlimit(resource.RLIMIT_NOFILE, (min(65535, hard), hard))
    except Exception:
        logger.debug("suppressed", exc_info=True)

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args, _ = ap.parse_known_args()

    if not CONFIG_PATH.exists():
        import sys
        print(f"ERROR: {CONFIG_PATH} not found", file=sys.stderr)
        return

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    hunt_cfg = config.get("hunt", {})
    if args.host:
        hunt_cfg["web_listen_host"] = args.host
    if args.port:
        hunt_cfg["web_listen_port"] = args.port

    try:
        asyncio.run(amain(config))
    except KeyboardInterrupt:
        pass
