#!/usr/bin/env bash
# setup_iptables.sh — transparent proxy redirects via iptables
#
# Usage: sudo ./setup_iptables.sh {start|stop|status} [--own-ip IP] [--exclude-uid UID] [--exclude-pid PID]
# Configure with environment variables:
#   REDIRECT_PORT  port the local transparent proxy listens on (default 17477)
#   REDIRECT_PORTS space-separated destination ports to redirect (default: ALL tcp)
#   OWN_IP         exclude this local IP from redirect (avoid VPN loops)
#   EXCLUDE_UID    exclude traffic from this UID (loop prevention)
#   EXCLUDE_CGROUP exclude traffic from this cgroup v2 path (modern, per-app
#                  loop prevention — replaces the removed --pid-owner)
#   CGROUP_PID     pid to move into EXCLUDE_CGROUP automatically (optional)
#
# Redirects all outbound TCP traffic (except local/reserved destinations) to
# the local transparent proxy. Loop prevention excludes the proxy's own
# upstream connections via --exclude-uid (run the proxy as a dedicated user).
# NOTE: the kernel's `owner` match has no --pid-owner on this platform, so
# --exclude-pid is resolved to that process's UID.

set -u

REDIRECT_PORT="${REDIRECT_PORT:-17477}"
REDIRECT_PORTS="${REDIRECT_PORTS:-}"
OWN_IP="${OWN_IP:-}"
EXCLUDE_UID="${EXCLUDE_UID:-}"
EXCLUDE_PID="${EXCLUDE_PID:-}"
EXCLUDE_CGROUP="${EXCLUDE_CGROUP:-}"
CGROUP_PID="${CGROUP_PID:-}"

CHAIN_NAME="HUNTPROXY_REDIRECT"
IPTABLES="iptables"
command -v iptables-legacy &>/dev/null && IPTABLES="iptables-legacy"

info() { echo "[*] $(date +%H:%M:%S) $*"; }

start_rules() {
  info "Setting up transparent redirects to port $REDIRECT_PORT (ports: ${REDIRECT_PORTS:-ALL tcp})"

  $IPTABLES -t nat -N "$CHAIN_NAME" 2>/dev/null || true
  $IPTABLES -t nat -F "$CHAIN_NAME"

  [[ -n "$EXCLUDE_UID" ]] && \
    $IPTABLES -t nat -A "$CHAIN_NAME" -m owner --uid-owner "$EXCLUDE_UID" -j RETURN

  # Modern per-application exclusion (replaces the removed --pid-owner): match
  # by cgroup v2 instead of PID. The proxy is placed in a dedicated cgroup so
  # ONLY its traffic is excluded from redirection — not the whole user.
  if [[ -n "$EXCLUDE_CGROUP" ]]; then
    local cg_path="/sys/fs/cgroup/${EXCLUDE_CGROUP#/}"
    if mkdir -p "$cg_path" 2>/dev/null && [[ -d "$cg_path" ]]; then
      if [[ -n "$CGROUP_PID" ]]; then
        echo "$CGROUP_PID" > "$cg_path/cgroup.procs" 2>/dev/null && \
          info "Moved pid $CGROUP_PID into cgroup $EXCLUDE_CGROUP"
      fi
    else
      info "WARNING: could not create cgroup $cg_path (need cgroup v2 + root)"
    fi
    $IPTABLES -t nat -A "$CHAIN_NAME" -m cgroup --path "$EXCLUDE_CGROUP" -j RETURN
  fi

  # Local/reserved destinations are never redirected (this is the
  # "except local" part of whole-machine interception).
  for net in 0.0.0.0/8 10.0.0.0/8 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 \
              192.168.0.0/16 224.0.0.0/4 240.0.0.0/4; do
    $IPTABLES -t nat -A "$CHAIN_NAME" -d "$net" -j RETURN
  done

  [[ -n "$OWN_IP" ]] && {
    $IPTABLES -t nat -A "$CHAIN_NAME" -d "$OWN_IP" -j RETURN
    $IPTABLES -t nat -A "$CHAIN_NAME" -s "$OWN_IP" -j RETURN
  }

  if [[ -n "$REDIRECT_PORTS" ]]; then
    for port in $REDIRECT_PORTS; do
      $IPTABLES -t nat -A "$CHAIN_NAME" -p tcp --dport "$port" \
        -j REDIRECT --to-port "$REDIRECT_PORT"
    done
  else
    # Default: redirect ALL outbound TCP (the proxy recovers the original
    # destination via SO_ORIGINAL_DST for any port).
    $IPTABLES -t nat -A "$CHAIN_NAME" -p tcp \
      -j REDIRECT --to-port "$REDIRECT_PORT"
  fi

  $IPTABLES -t nat -C OUTPUT -j "$CHAIN_NAME" 2>/dev/null || \
    $IPTABLES -t nat -A OUTPUT -j "$CHAIN_NAME"

  info "Done. Verify with: $IPTABLES -t nat -L $CHAIN_NAME -n -v"
}

stop_rules() {
  info "Removing transparent rules"
  $IPTABLES -t nat -D OUTPUT -j "$CHAIN_NAME" 2>/dev/null || true
  $IPTABLES -t nat -F "$CHAIN_NAME" 2>/dev/null || true
  $IPTABLES -t nat -X "$CHAIN_NAME" 2>/dev/null || true
  info "Done"
}

status_rules() {
  if $IPTABLES -t nat -L "$CHAIN_NAME" &>/dev/null; then
    echo "=== $CHAIN_NAME chain ==="
    $IPTABLES -t nat -L "$CHAIN_NAME" -n -v
  else
    echo "$CHAIN_NAME chain does not exist (transparent mode is OFF)"
  fi
}

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: must be root" >&2; exit 1
fi

# Parse optional args: --own-ip <ip> --exclude-uid <uid> --exclude-pid <pid>
ACTION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --own-ip)      OWN_IP="$2"; shift 2 ;;
    --exclude-uid) EXCLUDE_UID="$2"; shift 2 ;;
    --exclude-pid) EXCLUDE_PID="$2"; shift 2 ;;
    --exclude-cgroup) EXCLUDE_CGROUP="$2"; shift 2 ;;
    --cgroup-pid)  CGROUP_PID="$2"; shift 2 ;;
    --redirect-port) REDIRECT_PORT="$2"; shift 2 ;;
    start|stop|status) ACTION="$1"; shift ;;
    *) shift ;;
  esac
done
ACTION="${ACTION:-start}"

# --pid-owner is unavailable on this kernel; resolve the pid to its UID and
# use --uid-owner instead (run the proxy as a dedicated user for correct
# loop prevention).
if [[ -n "$EXCLUDE_PID" ]]; then
  if [[ -r "/proc/$EXCLUDE_PID/status" ]]; then
    EXCLUDE_PID_UID="$(awk '/^Uid:/{print $2; exit}' "/proc/$EXCLUDE_PID/status")"
    if [[ -n "$EXCLUDE_PID_UID" ]]; then
      info "Resolved --exclude-pid $EXCLUDE_PID -> uid $EXCLUDE_PID_UID (pid-owner unavailable; using uid-owner)"
      EXCLUDE_UID="${EXCLUDE_UID:-$EXCLUDE_PID_UID}"
    fi
  else
    info "WARNING: --exclude-pid $EXCLUDE_PID not found in /proc; ignoring"
  fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="$SCRIPT_DIR/data/transparent_state.json"

write_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  cat > "$STATE_FILE" <<EOF
{"active": $1, "applied_at": "$(date '+%Y-%m-%dT%H:%M:%S%z')", "own_ip": "$OWN_IP", "exclude_uid": "$EXCLUDE_UID", "exclude_pid": "$EXCLUDE_PID", "exclude_cgroup": "$EXCLUDE_CGROUP", "chain": "$CHAIN_NAME", "redirect_port": "$REDIRECT_PORT", "ports": "$REDIRECT_PORTS"}
EOF
  chmod 0644 "$STATE_FILE" 2>/dev/null || true
}

case "$ACTION" in
  start)  start_rules; write_state true ;;
  stop)   stop_rules; write_state false ;;
  status) status_rules ;;
  *) echo "Usage: $0 {start|stop|status} [--own-ip IP] [--exclude-uid UID] [--exclude-pid PID] [--exclude-cgroup PATH] [--cgroup-pid PID] [--redirect-port PORT]"; exit 1 ;;
esac
