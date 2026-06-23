#!/usr/bin/env bash
#
# huntproxy installer — one-line setup for Ubuntu 24.04
# Usage:  curl -fsSL https://raw.githubusercontent.com/siv237/huntproxy/main/install.sh | bash
#
set -euo pipefail

REPO="https://github.com/siv237/huntproxy.git"
INSTALL_DIR="${1:-$HOME/huntproxy}"
BRANCH="main"

c_ok()   { echo -e "  \033[32m✓\033[0m $*"; }
c_info() { echo -e "  \033[36m→\033[0m $*"; }
c_err()  { echo -e "  \033[31m✗\033[0m $*" >&2; }

# --- root check ---
if [ "$(id -u)" -eq 0 ]; then
    c_err "Don't run as root. Run as a normal user."
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
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip git curl > /dev/null 2>&1
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

# --- done ---
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  Installation complete!                      ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
echo "  Location:  $INSTALL_DIR"
echo ""
echo "  Quick start (foreground):"
echo "    cd $INSTALL_DIR && ./hunt.sh"
echo ""
echo "  Quick start (daemon):"
echo "    cd $INSTALL_DIR && ./daemon.sh start"
echo ""
echo "  Stop daemon:"
echo "    cd $INSTALL_DIR && ./daemon.sh stop"
echo ""
echo "  Web UI:  http://127.0.0.1:17177/"
echo ""
echo "  Public mode (listen on all interfaces):"
echo "    cd $INSTALL_DIR && ./hunt.sh --public"
echo ""
echo "  Run tests:"
echo "    cd $INSTALL_DIR && ./test.sh"
echo ""
