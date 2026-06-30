#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
HOST="${HUNT_HOST:-127.0.0.1}"
PORT="${HUNT_PORT:-17177}"

ARGS=()
KILL=false
for arg in "$@"; do
    case "$arg" in
        --public|--listen-all|-P)
            HOST="0.0.0.0"
            ;;
        --kill|-K)
            KILL=true
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
    "$VENV/bin/pip" install --upgrade pip setuptools wheel
    "$VENV/bin/pip" install PyYAML
    "$VENV/bin/python" -c "import yaml" || { echo "[!] Failed to install PyYAML" >&2; exit 1; }
    touch "$VENV/installed.flag"
fi

PID_FILE="$DIR/.hunt.pid"

existing_pids() {
    local pids=""

    # PID from previous run
    if [ -f "$PID_FILE" ]; then
        local old_pid
        old_pid=$(cat "$PID_FILE" 2>/dev/null) || true
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            pids="$pids $old_pid"
        fi
    fi

    # Anything listening on our port (prefer ss to only catch listeners, not clients)
    local port_pids
    port_pids=$(ss -ltnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || lsof -ti tcp:"$PORT" 2>/dev/null || true)
    if [ -n "$port_pids" ]; then
        pids="$pids $port_pids"
    fi

    # Deduplicate and filter
    echo "$pids" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u | tr '\n' ' '
}

check_existing() {
    local pids
    pids=$(existing_pids)
    [ -z "$pids" ] && return 0
    echo "[*] Port $PORT is already in use (pids:$pids). Use --kill to stop existing process(s) or run with a different port." >&2
    return 1
}

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
    local pids
    pids=$(existing_pids)
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

if [ "$KILL" = "true" ]; then
    kill_existing
else
    check_existing
fi

echo "[*] Starting hunt web UI at http://$HOST:$PORT/"
if [ "$HOST" = "0.0.0.0" ]; then
    echo "[*] Listening on all interfaces (public mode). Use --host 127.0.0.1 to restrict."
fi
echo "[*] Press Ctrl+C to stop."
# Raise file descriptor limit — parallel proxy checks (300+) through a
# channel open hundreds of sockets simultaneously and hit the default 1024.
ulimit -n 65535 2>/dev/null || true
# Write PID before exec: after exec Python inherits the same PID.
if [ -n "$PID_FILE" ]; then
    echo $$ > "$PID_FILE"
fi
exec "$VENV/bin/python" "$DIR/hunt.py" --host "$HOST" --port "$PORT" "${ARGS[@]}"
