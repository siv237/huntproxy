#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
HOST="${HUNT_HOST:-127.0.0.1}"
PORT="${HUNT_PORT:-17177}"

if [ ! -d "$VENV" ]; then
    echo "[*] Creating venv..."
    python3 -m venv "$VENV"
fi

if [ ! -f "$VENV/installed.flag" ]; then
    echo "[*] Installing dependencies..."
    "$VENV/bin/pip" install --quiet PyYAML 2>/dev/null || true
    touch "$VENV/installed.flag"
fi

echo "[*] Starting hunt web UI at http://$HOST:$PORT/"
echo "[*] Press Ctrl+C to stop."
exec "$VENV/bin/python" "$DIR/hunt.py" --host "$HOST" --port "$PORT"
