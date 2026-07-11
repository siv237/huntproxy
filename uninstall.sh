#!/usr/bin/env bash
#
# huntproxy uninstaller — removes everything the installer / runtime created:
#   - stops & disables the systemd service, deletes its unit file
#   - removes the transparent-redirect iptables chain (HUNTPROXY_REDIRECT)
#   - removes the dedicated cgroup v2 path (/sys/fs/cgroup/huntproxy)
#   - deletes the install directory (code, venv, data, logs)
#
# Usage:  sudo ./uninstall.sh [--yes] [INSTALL_DIR]
#   --yes           do not prompt for confirmation
#   INSTALL_DIR     path to remove (default /opt/huntproxy)
#
set -u

INSTALL_DIR="/opt/huntproxy"
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    -y|--yes) FORCE=1; shift ;;
    --yes=*)  FORCE=1; shift ;;
    -*)       shift ;;
    *)        INSTALL_DIR="$1"; shift ;;
  esac
done

SERVICE="huntproxy"
CHAIN="HUNTPROXY_REDIRECT"
CGROUP="/sys/fs/cgroup/huntproxy"

c_ok()   { echo -e "  \033[32m✓\033[0m $*"; }
c_info() { echo -e "  \033[36m→\033[0m $*"; }
c_err()  { echo -e "  \033[31m✗\033[0m $*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
  c_err "This uninstaller must be run as root. Try:  sudo ./uninstall.sh"
  exit 1
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║         huntproxy uninstaller          ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  Will remove:"
echo "    - systemd service : $SERVICE"
echo "    - iptables chain  : $CHAIN (nat/OUTPUT)"
echo "    - cgroup v2 path  : $CGROUP"
echo "    - install dir     : $INSTALL_DIR"
echo ""

if [ "$FORCE" -ne 1 ]; then
  read -r -p "  Continue? [y/N] " ans
  case "$ans" in
    y|Y) ;;
    *) echo "  Aborted."; exit 1 ;;
  esac
fi

# --- 1. stop & disable systemd service ---
c_info "Stopping systemd service..."
if systemctl list-unit-files 2>/dev/null | grep -q "^$SERVICE.service"; then
  systemctl stop "$SERVICE" 2>/dev/null || true
  systemctl disable "$SERVICE" 2>/dev/null || true
  rm -f "/etc/systemd/system/$SERVICE.service"
  systemctl daemon-reload 2>/dev/null || true
  c_ok "systemd service removed"
else
  c_info "systemd service not present — skipping"
fi

# --- 2. remove iptables transparent-redirect rules ---
c_info "Removing iptables rules..."
for IPT in iptables iptables-legacy; do
  command -v "$IPT" &>/dev/null || continue
  "$IPT" -t nat -D OUTPUT -j "$CHAIN" 2>/dev/null || true
  "$IPT" -t nat -F "$CHAIN" 2>/dev/null || true
  "$IPT" -t nat -X "$CHAIN" 2>/dev/null || true
done
# Also ask the script itself if it is still present (covers cgroup args).
if [ -x "$INSTALL_DIR/setup_iptables.sh" ]; then
  ( cd "$INSTALL_DIR" && ./setup_iptables.sh stop >/dev/null 2>&1 ) || true
fi
if ! iptables -t nat -L "$CHAIN" >/dev/null 2>&1; then
  c_ok "iptables chain removed"
else
  c_info "iptables chain still present (review manually)"
fi

# --- 3. remove cgroup v2 path ---
if [ -d "$CGROUP" ]; then
  c_info "Removing cgroup $CGROUP..."
  # Move any remaining procs back to the root cgroup so the dir can be removed.
  for p in $(cat "$CGROUP/cgroup.procs" 2>/dev/null); do
    echo "$p" > /sys/fs/cgroup/cgroup.procs 2>/dev/null || true
  done
  rmdir "$CGROUP" 2>/dev/null || rm -rf "$CGROUP" 2>/dev/null || true
  [ -d "$CGROUP" ] && c_info "cgroup could not be removed (still present)" \
                   || c_ok "cgroup removed"
else
  c_info "cgroup not present — skipping"
fi

# --- 4. delete install directory ---
if [ -d "$INSTALL_DIR" ]; then
  c_info "Deleting $INSTALL_DIR..."
  rm -rf "$INSTALL_DIR"
  [ -d "$INSTALL_DIR" ] && c_err "failed to remove $INSTALL_DIR" \
                          || c_ok "install directory removed"
else
  c_info "install directory not present — skipping"
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  Uninstall complete                    ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  huntproxy has been removed. Reinstall any time with:"
echo "    curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | sudo bash"
echo ""
