#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
HOST="${HUNT_HOST:-127.0.0.1}"
PORT="${HUNT_PORT:-17177}"

ARGS=()
for arg in "$@"; do
    case "$arg" in
        --public|--listen-all|-P)
            HOST="0.0.0.0"
            ;;
        *)
            ARGS+=("$arg")
            ;;
    esac
done

if [ ! -d "$VENV" ]; then
    echo "[*] Creating venv..."
    python3 -m venv "$VENV"
fi

if [ ! -f "$VENV/installed.flag" ]; then
    echo "[*] Installing dependencies..."
    "$VENV/bin/pip" install --quiet PyYAML 2>/dev/null || true
    touch "$VENV/installed.flag"
fi

PID_FILE="$DIR/.hunt.pid"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[*] Stopping existing daemon (pid $(cat "$PID_FILE"))..."
    kill "$(cat "$PID_FILE")" 2>/dev/null || true
    sleep 0.5
    rm -f "$PID_FILE"
    echo "[*] Daemon stopped."
fi

echo "[*] Starting hunt web UI at http://$HOST:$PORT/"
if [ "$HOST" = "0.0.0.0" ]; then
    echo "[*] Listening on all interfaces (public mode). Use --host 127.0.0.1 to restrict."
fi
echo "[*] Press Ctrl+C to stop."
exec "$VENV/bin/python" "$DIR/hunt.py" --host "$HOST" --port "$PORT" "${ARGS[@]}"
