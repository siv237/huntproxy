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

kill_pids() {
    local pids="$1"
    local sig="${2:-TERM}"
    [ -z "$pids" ] && return 0
    for pid in $pids; do
        [ "$pid" = "$$" ] && continue
        kill -s "$sig" "$pid" 2>/dev/null || true
    done
}

kill_existing() {
    local pids=""

    # PID from previous run
    if [ -f "$PID_FILE" ]; then
        local old_pid
        old_pid=$(cat "$PID_FILE" 2>/dev/null) || true
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            pids="$pids $old_pid"
        fi
    fi

    # Anything listening on our port
    local port_pids
    port_pids=$(lsof -ti tcp:"$PORT" 2>/dev/null || ss -ltnp 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
    if [ -n "$port_pids" ]; then
        pids="$pids $port_pids"
    fi

    # Any other hunt.py processes from this project directory
    local hunt_pids
    hunt_pids=$(pgrep -f "python.*$DIR/hunt\.py" 2>/dev/null || true)
    if [ -n "$hunt_pids" ]; then
        pids="$pids $hunt_pids"
    fi

    # Deduplicate and filter
    pids=$(echo "$pids" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u | tr '\n' ' ')
    [ -z "$pids" ] && return 0

    echo "[*] Stopping existing hunt processes (pids:$pids)..."
    kill_pids "$pids" TERM
    for _ in {1..10}; do
        local still_alive=""
        for pid in $pids; do
            kill -0 "$pid" 2>/dev/null && still_alive="$still_alive $pid"
        done
        [ -z "$still_alive" ] && break
        sleep 0.5
    done
    kill_pids "$still_alive" KILL
    sleep 0.2
    rm -f "$PID_FILE"
    echo "[*] Existing processes stopped."
}

kill_existing

echo "[*] Starting hunt web UI at http://$HOST:$PORT/"
if [ "$HOST" = "0.0.0.0" ]; then
    echo "[*] Listening on all interfaces (public mode). Use --host 127.0.0.1 to restrict."
fi
echo "[*] Press Ctrl+C to stop."
exec "$VENV/bin/python" "$DIR/hunt.py" --host "$HOST" --port "$PORT" "${ARGS[@]}"
