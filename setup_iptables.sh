#!/usr/bin/env bash
# setup_iptables.sh — transparent proxy redirects via iptables
#
# Usage:
#   sudo ./setup_iptables.sh {start|stop|status} [options]
#
# Whole-machine mode (default): redirect ALL outbound TCP (except local/reserved
# destinations) to the local transparent proxy.
#   --own-ip IP            exclude this local IP from redirect (avoid VPN loops)
#   --exclude-uid UID      exclude traffic from this UID (loop prevention)
#   --exclude-cgroup PATH  exclude traffic from this cgroup v2 path
#   --cgroup-pid PID       move PID into EXCLUDE_CGROUP automatically
#
# Selective mode (--selective): redirect ONLY destinations listed in
# --ipset-spec. Each line is either ``auto IP`` (redirect all TCP for that IP)
# or ``PORT IP`` (redirect only that port). One ipset is built per policy.
# Use --drop-quic to also drop UDP/443 so QUIC clients fall back to TCP.
#   --iface IFACE  restrict redirects to the outbound interface (auto-detected
#                  from the default route when omitted).
#
# Configure with environment variables:
#   REDIRECT_PORT  port the local transparent proxy listens on (default 17477)
#   REDIRECT_PORTS space/comma-separated destination ports (default: ALL tcp)

set -u

REDIRECT_PORT="${REDIRECT_PORT:-17477}"
REDIRECT_PORTS="${REDIRECT_PORTS:-}"
OWN_IP="${OWN_IP:-}"
EXCLUDE_UID="${EXCLUDE_UID:-}"
EXCLUDE_PID="${EXCLUDE_PID:-}"
EXCLUDE_CGROUP="${EXCLUDE_CGROUP:-}"
CGROUP_PID="${CGROUP_PID:-}"
IFACE="${IFACE:-}"
SELECTIVE=0
IPSET_SPEC=""
DROP_QUIC=0

CHAIN_NAME="HUNTPROXY_REDIRECT"
SELECTIVE_CHAIN="HUNTPROXY_SELECTIVE"
QUIC_CHAIN="HUNTPROXY_SELECTIVE_QUIC"
IPSET_PREFIX="huntproxy_sel"
IPTABLES="iptables"
command -v iptables-legacy &>/dev/null && IPTABLES="iptables-legacy"

info() { echo "[*] $(date +%H:%M:%S) $*"; }

have_ipset() { command -v ipset &>/dev/null; }

detect_iface() {
  ip route get 1.1.1.1 2>/dev/null | sed -n 's/.*dev \([^ ]*\).*/\1/p' | head -1
}

ensure_exclude_cgroup() {
  [[ -z "$EXCLUDE_CGROUP" ]] && return 0
  local cg_path="/sys/fs/cgroup/${EXCLUDE_CGROUP#/}"
  if mkdir -p "$cg_path" 2>/dev/null && [[ -d "$cg_path" ]]; then
    if [[ -n "$CGROUP_PID" ]]; then
      echo "$CGROUP_PID" > "$cg_path/cgroup.procs" 2>/dev/null && \
        info "Moved pid $CGROUP_PID into cgroup $EXCLUDE_CGROUP"
    fi
  else
    info "WARNING: could not create cgroup $cg_path (need cgroup v2 + root)"
  fi
}

add_exclusions() {
  # Return proxy's own traffic from a chain so it never loops back into the
  # transparent listener. $1 = chain, $2 = table.
  local chain="$1" table="$2"
  [[ -n "$EXCLUDE_UID" ]] && \
    $IPTABLES -t "$table" -A "$chain" -m owner --uid-owner "$EXCLUDE_UID" -j RETURN
  [[ -n "$EXCLUDE_CGROUP" ]] && \
    $IPTABLES -t "$table" -A "$chain" -m cgroup --path "$EXCLUDE_CGROUP" -j RETURN
  return 0
}

start_selective_rules() {
  info "Setting up SELECTIVE redirect to port $REDIRECT_PORT (iface: ${IFACE:-any})"
  local use_ipset=0
  have_ipset && use_ipset=1
  local -a o=()
  [[ -n "$IFACE" ]] && o=(-o "$IFACE")
  ensure_exclude_cgroup

  # Rebuild from scratch: drop any previous selective chain/jump and the QUIC
  # chain first, so a restart never duplicates rules or leaves a QUIC jump
  # behind when drop-quic is now off.
  $IPTABLES -t nat -D OUTPUT -j "$SELECTIVE_CHAIN" 2>/dev/null || true
  $IPTABLES -t nat -F "$SELECTIVE_CHAIN" 2>/dev/null || true
  $IPTABLES -t nat -X "$SELECTIVE_CHAIN" 2>/dev/null || true
  $IPTABLES -t filter -D OUTPUT -j "$QUIC_CHAIN" 2>/dev/null || true
  $IPTABLES -t filter -F "$QUIC_CHAIN" 2>/dev/null || true
  $IPTABLES -t filter -X "$QUIC_CHAIN" 2>/dev/null || true

  $IPTABLES -t nat -N "$SELECTIVE_CHAIN" 2>/dev/null || true
  $IPTABLES -t nat -F "$SELECTIVE_CHAIN"
  add_exclusions "$SELECTIVE_CHAIN" nat

  declare -A SETNAME=()
  local -a ORDER=()
  local allset="${IPSET_PREFIX}_all"
  if [[ -z "$IPSET_SPEC" || ! -f "$IPSET_SPEC" ]]; then
    info "WARNING: no --ipset-spec file — nothing to redirect"
  fi
  if [[ "$use_ipset" == "1" ]]; then
    # Drop any stale sets from a previous apply (e.g. a port no longer used),
    # then rebuild fresh from the spec.
    for s in $(ipset list -n 2>/dev/null | grep -E "^${IPSET_PREFIX}_"); do
      ipset destroy "$s" 2>/dev/null || true
    done
    ipset create "$allset" hash:ip -exist
    ipset flush "$allset"
  fi

  if [[ "$use_ipset" == "1" ]]; then
    while read -r key ip; do
      [[ -z "$key" || -z "$ip" ]] && continue
      local name
      if [[ "$key" == "auto" ]]; then name="${IPSET_PREFIX}_auto"; else name="${IPSET_PREFIX}_p${key//[^0-9]/}"; fi
      if [[ -z "${SETNAME[$key]:-}" ]]; then
        SETNAME[$key]="$name"; ORDER+=("$key")
        ipset create "$name" hash:ip -exist
        ipset flush "$name"
      fi
      ipset add "${SETNAME[$key]}" "$ip" -exist
      ipset add "$allset" "$ip" -exist
    done < "$IPSET_SPEC"
    for key in "${ORDER[@]}"; do
      local sname="${SETNAME[$key]}"
      if [[ "$key" == "auto" ]]; then
        $IPTABLES -t nat -A "$SELECTIVE_CHAIN" "${o[@]}" -m set --match-set "$sname" dst \
          -p tcp -j REDIRECT --to-port "$REDIRECT_PORT"
      else
        $IPTABLES -t nat -A "$SELECTIVE_CHAIN" "${o[@]}" -m set --match-set "$sname" dst \
          -p tcp --dport "$key" -j REDIRECT --to-port "$REDIRECT_PORT"
      fi
    done
  else
    info "WARNING: ipset not found — falling back to individual destination rules"
    for net in 127.0.0.0/8 10.0.0.0/8 169.254.0.0/16 172.16.0.0/12 \
               192.168.0.0/16 224.0.0.0/4 240.0.0.0/4; do
      $IPTABLES -t nat -A "$SELECTIVE_CHAIN" -d "$net" -j RETURN
    done
    if [[ -n "$IPSET_SPEC" && -f "$IPSET_SPEC" ]]; then
      while read -r key ip; do
        [[ -z "$key" || -z "$ip" ]] && continue
        if [[ "$key" == "auto" ]]; then
          $IPTABLES -t nat -A "$SELECTIVE_CHAIN" "${o[@]}" -p tcp -d "$ip" \
            -j REDIRECT --to-port "$REDIRECT_PORT"
        else
          $IPTABLES -t nat -A "$SELECTIVE_CHAIN" "${o[@]}" -p tcp -d "$ip" --dport "$key" \
            -j REDIRECT --to-port "$REDIRECT_PORT"
        fi
      done < "$IPSET_SPEC"
    fi
  fi

  $IPTABLES -t nat -C OUTPUT -j "$SELECTIVE_CHAIN" 2>/dev/null || \
    $IPTABLES -t nat -A OUTPUT -j "$SELECTIVE_CHAIN"

  if [[ "$DROP_QUIC" == "1" ]]; then
    $IPTABLES -t filter -N "$QUIC_CHAIN" 2>/dev/null || true
    $IPTABLES -t filter -F "$QUIC_CHAIN"
    add_exclusions "$QUIC_CHAIN" filter
    if [[ "$use_ipset" == "1" ]]; then
      $IPTABLES -t filter -A "$QUIC_CHAIN" "${o[@]}" -m set --match-set "$allset" dst \
        -p udp --dport 443 -j DROP
    elif [[ -n "$IPSET_SPEC" && -f "$IPSET_SPEC" ]]; then
      while read -r key ip; do
        [[ -z "$ip" ]] && continue
        $IPTABLES -t filter -A "$QUIC_CHAIN" "${o[@]}" -p udp -d "$ip" --dport 443 -j DROP
      done < "$IPSET_SPEC"
    fi
    $IPTABLES -t filter -C OUTPUT -j "$QUIC_CHAIN" 2>/dev/null || \
      $IPTABLES -t filter -A OUTPUT -j "$QUIC_CHAIN"
  fi

  info "Done. Verify with: $IPTABLES -t nat -L $SELECTIVE_CHAIN -n -v"
}

start_rules() {
  if [[ "$SELECTIVE" == "1" ]]; then
    start_selective_rules
    return
  fi
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

  $IPTABLES -t nat -D OUTPUT -j "$SELECTIVE_CHAIN" 2>/dev/null || true
  $IPTABLES -t nat -F "$SELECTIVE_CHAIN" 2>/dev/null || true
  $IPTABLES -t nat -X "$SELECTIVE_CHAIN" 2>/dev/null || true

  $IPTABLES -t filter -D OUTPUT -j "$QUIC_CHAIN" 2>/dev/null || true
  $IPTABLES -t filter -F "$QUIC_CHAIN" 2>/dev/null || true
  $IPTABLES -t filter -X "$QUIC_CHAIN" 2>/dev/null || true

  if have_ipset; then
    # Remove every set this project ever created, including the legacy
    # single-set name from older versions.
    for s in $(ipset list -n 2>/dev/null | grep -E "^huntproxy_(sel|selective)"); do
      ipset destroy "$s" 2>/dev/null || true
    done
  fi
  info "Done"
}

status_rules() {
  if $IPTABLES -t nat -L "$CHAIN_NAME" &>/dev/null; then
    echo "=== $CHAIN_NAME chain ==="
    $IPTABLES -t nat -L "$CHAIN_NAME" -n -v
  else
    echo "$CHAIN_NAME chain does not exist (whole-machine mode is OFF)"
  fi
  if $IPTABLES -t nat -L "$SELECTIVE_CHAIN" &>/dev/null; then
    echo "=== $SELECTIVE_CHAIN chain ==="
    $IPTABLES -t nat -L "$SELECTIVE_CHAIN" -n -v
  else
    echo "$SELECTIVE_CHAIN chain does not exist (selective mode is OFF)"
  fi
  if have_ipset; then
    for s in $(ipset list -n 2>/dev/null | grep -E "^${IPSET_PREFIX}_"); do
      echo "=== ipset $s ==="
      ipset list "$s" 2>/dev/null | head -n 20
    done
  fi
}

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: must be root" >&2; exit 1
fi

# Parse optional args.
ACTION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --own-ip)      OWN_IP="$2"; shift 2 ;;
    --exclude-uid) EXCLUDE_UID="$2"; shift 2 ;;
    --exclude-pid) EXCLUDE_PID="$2"; shift 2 ;;
    --exclude-cgroup) EXCLUDE_CGROUP="$2"; shift 2 ;;
    --cgroup-pid)  CGROUP_PID="$2"; shift 2 ;;
    --redirect-port) REDIRECT_PORT="$2"; shift 2 ;;
    --selective)   SELECTIVE=1; shift ;;
    --ipset-spec)  IPSET_SPEC="$2"; shift 2 ;;
    --drop-quic)   DROP_QUIC=1; shift ;;
    --iface)       IFACE="$2"; shift 2 ;;
    start|stop|status) ACTION="$1"; shift ;;
    *) shift ;;
  esac
done
ACTION="${ACTION:-start}"

# Selective mode: restrict redirects to the outbound internet interface
# (like `-o eth0`), auto-detected from the default route unless given.
if [[ "$SELECTIVE" == "1" && -z "$IFACE" ]]; then
  IFACE="$(detect_iface)"
  [[ -n "$IFACE" ]] && info "Auto-detected outbound interface: $IFACE"
fi

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
MODE="all"
[[ "$SELECTIVE" == "1" ]] && MODE="selective"

write_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  cat > "$STATE_FILE" <<EOF
{"active": $1, "mode": "$MODE", "applied_at": "$(date '+%Y-%m-%dT%H:%M:%S%z')", "own_ip": "$OWN_IP", "exclude_uid": "$EXCLUDE_UID", "exclude_pid": "$EXCLUDE_PID", "exclude_cgroup": "$EXCLUDE_CGROUP", "iface": "$IFACE", "chain": "$CHAIN_NAME", "redirect_port": "$REDIRECT_PORT", "ports": "$REDIRECT_PORTS"}
EOF
  chmod 0644 "$STATE_FILE" 2>/dev/null || true
}

case "$ACTION" in
  start)  start_rules; write_state true ;;
  stop)   stop_rules; write_state false ;;
  status) status_rules ;;
  *) echo "Usage: $0 {start|stop|status} [--selective --ipset-spec FILE [--iface IFACE] [--drop-quic]] [--own-ip IP] [--exclude-uid UID] [--exclude-pid PID] [--exclude-cgroup PATH] [--cgroup-pid PID] [--redirect-port PORT]"; exit 1 ;;
esac
