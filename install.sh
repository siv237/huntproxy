#!/usr/bin/env bash
#
# huntproxy installer — one-line setup for Ubuntu 24.04
# Usage:  curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
#
set -euo pipefail

REPO="https://github.com/siv237/huntproxy.git"
INSTALL_DIR="${1:-/opt/huntproxy}"
BRANCH="main"

c_ok()   { echo -e "  \033[32m✓\033[0m $*"; }
c_info() { echo -e "  \033[36m→\033[0m $*"; }
c_err()  { echo -e "  \033[31m✗\033[0m $*" >&2; }

# --- root check ---
if [ "$(id -u)" -ne 0 ]; then
    c_err "This installer must be run as root. Try:  curl ... | sudo bash"
    exit 1
fi

# --- detect OS ---
if [ -f /etc/os-release ]; then
    . /etc/os-release
fi
if [ "${ID:-}" != "ubuntu" ] && [ "${ID_LIKE:-}" != *"ubuntu"* ]; then
    c_info "This installer targets Ubuntu 24.04. You seem to be on ${PRETTY_NAME:-unknown}."
    c_info "Continuing anyway, but apt packages may differ."
fi

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        huntproxy installer            ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# --- 1. system deps ---
c_info "Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl > /dev/null 2>&1
c_ok "System packages installed"

# --- 2. clone / update ---
if [ -d "$INSTALL_DIR/.git" ]; then
    c_info "Updating existing install at $INSTALL_DIR..."
    git -C "$INSTALL_DIR" fetch --quiet origin "$BRANCH"
    git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" --quiet
    c_ok "Repository updated"
else
    c_info "Cloning huntproxy to $INSTALL_DIR..."
    git clone --depth 1 -b "$BRANCH" "$REPO" "$INSTALL_DIR" --quiet
    c_ok "Repository cloned"
fi

cd "$INSTALL_DIR"

# --- 3. venv + deps ---
c_info "Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
c_ok "Virtual environment ready"

c_info "Installing Python dependencies..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt 2>/dev/null || .venv/bin/pip install --quiet PyYAML
touch .venv/installed.flag
c_ok "Python dependencies installed"

# --- 4. scripts executable ---
chmod +x hunt.sh daemon.sh test.sh 2>/dev/null || true
c_ok "Scripts made executable"

# --- 5. create data dir ---
mkdir -p data
c_ok "Data directory ready"

# --- 6. create systemd service ---
c_info "Creating systemd service..."
cat > /etc/systemd/system/huntproxy.service << EOF
[Unit]
Description=huntproxy — proxy hunter and manager
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/hunt.py --host 127.0.0.1 --port 17177
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
c_ok "systemd service created (huntproxy.service)"

# --- done ---
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  Installation complete!                      ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
echo "  Location:  $INSTALL_DIR"
echo ""
echo "  Start as service:"
echo "    systemctl start huntproxy"
echo "    systemctl enable huntproxy   (auto-start on boot)"
echo ""
echo "  Check status:"
echo "    systemctl status huntproxy"
echo ""
echo "  Stop / restart:"
echo "    systemctl stop huntproxy"
echo "    systemctl restart huntproxy"
echo ""
echo "  Or run manually (foreground):"
echo "    cd $INSTALL_DIR && ./hunt.sh"
echo ""
echo "  Public mode (listen on all interfaces):"
echo "    cd $INSTALL_DIR && ./hunt.sh --public"
echo ""
echo "  Web UI:  http://127.0.0.1:17177/"
echo "  Logs:    journalctl -u huntproxy -f"
echo ""
echo "  Run tests:"
echo "    cd $INSTALL_DIR && ./test.sh"
echo ""
