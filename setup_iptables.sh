#!/usr/bin/env bash
# setup_iptables.sh — transparent proxy redirects via iptables
#
# Usage: sudo ./setup_iptables.sh {start|stop|status}
# Configure with environment variables:
#   REDIRECT_PORT  port the local transparent proxy listens on (default 17477)
#   REDIRECT_PORTS space-separated destination ports to redirect (default "80 443")
#   OWN_IP         exclude this local IP from redirect (avoid VPN loops)
#   EXCLUDE_UID    exclude traffic from this UID

set -u

REDIRECT_PORT="${REDIRECT_PORT:-17477}"
REDIRECT_PORTS="${REDIRECT_PORTS:-80 443}"
OWN_IP="${OWN_IP:-}"
EXCLUDE_UID="${EXCLUDE_UID:-}"

CHAIN_NAME="HUNTPROXY_REDIRECT"
IPTABLES="iptables"
command -v iptables-legacy &>/dev/null && IPTABLES="iptables-legacy"

info() { echo "[*] $(date +%H:%M:%S) $*"; }

start_rules() {
  info "Setting up transparent redirects to port $REDIRECT_PORT (ports: $REDIRECT_PORTS)"

  $IPTABLES -t nat -N "$CHAIN_NAME" 2>/dev/null || true
  $IPTABLES -t nat -F "$CHAIN_NAME"

  [[ -n "$EXCLUDE_UID" ]] && \
    $IPTABLES -t nat -A "$CHAIN_NAME" -m owner --uid-owner "$EXCLUDE_UID" -j RETURN

  for net in 0.0.0.0/8 10.0.0.0/8 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 \
             192.168.0.0/16 224.0.0.0/4 240.0.0.0/4; do
    $IPTABLES -t nat -A "$CHAIN_NAME" -d "$net" -j RETURN
  done

  [[ -n "$OWN_IP" ]] && {
    $IPTABLES -t nat -A "$CHAIN_NAME" -d "$OWN_IP" -j RETURN
    $IPTABLES -t nat -A "$CHAIN_NAME" -s "$OWN_IP" -j RETURN
  }

  for port in $REDIRECT_PORTS; do
    $IPTABLES -t nat -A "$CHAIN_NAME" -p tcp --dport "$port" \
      -j REDIRECT --to-port "$REDIRECT_PORT"
  done

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

case "${1:-}" in
  start)  start_rules ;;
  stop)   stop_rules ;;
  status) status_rules ;;
  *) echo "Usage: $0 {start|stop|status}"; exit 1 ;;
esac
