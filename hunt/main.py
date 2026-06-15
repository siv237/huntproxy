"""Functional split of the huntproxy backend."""

import argparse
import asyncio
import yaml
from hunt.constants import CONFIG_PATH, DATA_DIR
from hunt.logging_config import setup_logging
from hunt.server import HuntServer
from hunt.state import HuntState

async def amain(config: dict):
    hunt_cfg = config.get("hunt", {})
    host = hunt_cfg.get("web_listen_host", "127.0.0.1")
    port = hunt_cfg.get("web_listen_port", 17177)

    state = HuntState(config)
    server = HuntServer(state, host, port)
    state.proxy_runner = server.proxy

    # Restore services that were running before restart
    restored = []
    if getattr(state, '_hunt_running', False):
        if state.start_hunt():
            restored.append("hunt")
    if getattr(state, '_proxy_running', False):
        proxy_port = getattr(state, '_proxy_port', 17277)
        await server.proxy.start(proxy_port)
        restored.append(f"proxy:{proxy_port}")
    if getattr(state, '_socks5_running', False):
        socks5_port = getattr(state, '_socks5_port', 17278)
        await server.socks5.start(socks5_port)
        restored.append(f"socks5:{socks5_port}")
    if getattr(state, '_proxy_direct_mode', False):
        server.proxy.direct_mode = True
    if getattr(state, '_proxy_active_addr', None):
        server.proxy.select(state._proxy_active_addr)
    if restored:
        state._emit(f"Restored services after restart: {', '.join(restored)}", "info")

    # Start periodic history recording (every 60s)
    asyncio.create_task(state._history_loop())

    # Start periodic IP blacklist refresh
    if state.ip_blacklist_enabled:
        asyncio.create_task(state._ip_blacklist_loop())

    print("=" * 56)
    print(f"  huntproxy HUNT — web UI: http://{host}:{port}/")
    print(f"  data dir: {DATA_DIR}")
    print("  Ctrl+C to stop")
    print("=" * 56)

    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    finally:
        state._save_state()
        state._save_working_file()
        await server.stop()

def main():
    setup_logging()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args, _ = ap.parse_known_args()

    if not CONFIG_PATH.exists():
        print(f"ERROR: {CONFIG_PATH} not found", file=__import__("sys").stderr)
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
