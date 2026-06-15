#!/usr/bin/env bash
# install.sh — install huntproxy as a systemd service
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="huntproxy"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/lib/huntproxy}"
BIN_DIR="${BIN_DIR:-/usr/local/bin}"

info() { echo "[*] $(date +%H:%M:%S) $*"; }
need_root() { [[ $EUID -eq 0 ]] || { echo "must be root" >&2; exit 1; }; }

install() {
  need_root
  info "Installing to $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR/data"
  cp -r "$SCRIPT_DIR"/{hunt.py,hunt,hunt.sh,daemon.sh,config.yaml,requirements.txt} "$INSTALL_DIR/"

  ln -sf "$INSTALL_DIR/hunt.sh" "$BIN_DIR/huntproxy"
  ln -sf "$SCRIPT_DIR/setup_iptables.sh" "$BIN_DIR/huntproxy-iptables"
  chmod +x "$BIN_DIR/huntproxy" "$BIN_DIR/huntproxy-iptables"

  pip3 install --break-system-packages -r "$INSTALL_DIR/requirements.txt" >/dev/null 2>&1 || \
    pip3 install -r "$INSTALL_DIR/requirements.txt" >/dev/null 2>&1 || true

  cat > "$SYSTEMD_DIR/$SERVICE_NAME.service" << EOF
[Unit]
Description=huntproxy — cascading proxy with transparent mode
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/hunt.sh
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME" 2>/dev/null || true
  systemctl restart "$SERVICE_NAME" 2>/dev/null || true

  info "Installed."
  echo
  echo "  systemctl {start|stop|status|restart} $SERVICE_NAME"
  echo "  journalctl -u $SERVICE_NAME -f"
  echo "  $BIN_DIR/huntproxy {status|list|refresh|blacklist}"
  echo "  $BIN_DIR/huntproxy-iptables {start|stop|status}"
}

uninstall() {
  need_root
  systemctl stop "$SERVICE_NAME" 2>/dev/null || true
  systemctl disable "$SERVICE_NAME" 2>/dev/null || true
  rm -f "$SYSTEMD_DIR/$SERVICE_NAME.service"
  rm -f "$BIN_DIR/huntproxy" "$BIN_DIR/huntproxy-iptables"
  rm -rf "$INSTALL_DIR"
  systemctl daemon-reload
  info "Uninstalled."
}

case "${1:-install}" in
  install) install ;;
  uninstall) uninstall ;;
  *) echo "Usage: $0 {install|uninstall}"; exit 1 ;;
esac
