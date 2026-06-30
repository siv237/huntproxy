#!/usr/bin/env bash
# huntproxy daemon — manage hunt proxy server as a background daemon
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
PID_FILE="$DIR/.hunt.pid"
LOG_FILE="$DIR/data/daemon.log"
HOST="${HUNT_HOST:-127.0.0.1}"
PORT="${HUNT_PORT:-17177}"

info()  { echo "[$(date +%H:%M:%S)] $*"; }
ok()    { echo "  OK: $*"; }
fail()  { echo "  FAIL: $*" >&2; }

ensure_venv() {
    if [ ! -d "$VENV" ]; then
        info "Creating venv..."
        python3 -m venv "$VENV"
    fi
    if [ ! -f "$VENV/installed.flag" ]; then
        info "Installing deps..."
        "$VENV/bin/pip" install --upgrade pip setuptools wheel
        "$VENV/bin/pip" install PyYAML
        "$VENV/bin/python" -c "import yaml" || { fail "Cannot install PyYAML"; return 1; }
        touch "$VENV/installed.flag"
    fi
}

is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

cmd_status() {
    if is_running; then
        ok "hunt running (pid $(cat "$PID_FILE") on $HOST:$PORT)"
    else
        info "hunt NOT running"
    fi
}

cmd_start() {
    if is_running; then
        ok "already running (pid $(cat "$PID_FILE"))"
        return
    fi
    ensure_venv
    info "Starting hunt daemon on $HOST:$PORT ..."
    ulimit -n 65535 2>/dev/null || true
    nohup "$VENV/bin/python" "$DIR/hunt.py" --host "$HOST" --port "$PORT" \
        >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        ok "started (pid $pid)"
    else
        fail "start failed, check $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

cmd_stop() {
    if ! is_running; then
        info "hunt not running"
        rm -f "$PID_FILE"
        return
    fi
    local pid=$(cat "$PID_FILE")
    info "Stopping hunt (pid $pid) ..."
    kill "$pid" 2>/dev/null || true
    for i in {1..10}; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    ok "stopped"
}

cmd_restart() {
    cmd_stop
    sleep 0.5
    cmd_start
}

cmd_log() {
    local n="${1:-20}"
    if [ -f "$LOG_FILE" ]; then
        tail -n "$n" "$LOG_FILE"
    else
        echo "(no log yet)"
    fi
}

case "${1:-start}" in
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    restart)  cmd_restart ;;
    status)   cmd_status ;;
    log)      cmd_log "${2:-20}" ;;
    *) echo "Usage: $0 {start|stop|restart|status|log [N]}"
       exit 1 ;;
esac
