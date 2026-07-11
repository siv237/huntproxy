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
c_info "Installing system dependencies (python3, venv, git, curl)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip git curl
c_ok "System packages installed"

# --- 2. clone / update ---
mkdir -p "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
    MODE="update"
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║           UPDATE MODE                 ║"
    echo "  ╚══════════════════════════════════════╝"
    c_info "Existing install detected at $INSTALL_DIR — running UPDATE"
    cd "$INSTALL_DIR"

    # Snapshot the currently-deployed commit so we can later tell which
    # tracked files the upstream update actually changed.
    OLD_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "")

    # Back up any LOCAL tracked modifications BEFORE reset --hard, so a
    # customized config.yaml (or other tracked file) is never silently lost.
    mkdir -p data
    BACKED_UP=""
    if [ -n "$(git diff --name-only HEAD 2>/dev/null)" ]; then
        BACKUP_DIR="data/pre-update-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        for f in $(git diff --name-only HEAD 2>/dev/null); do
            mkdir -p "$BACKUP_DIR/$(dirname "$f")"
            cp -a "$f" "$BACKUP_DIR/$f"
            BACKED_UP="$BACKED_UP $f"
        done
        c_ok "Local changes backed up to $BACKUP_DIR"
    fi

    # Decide whether the venv must be rebuilt: only if requirements changed.
    OLD_REQ_HASH=$(git show HEAD:requirements.txt 2>/dev/null | sha256sum | cut -d' ' -f1)
    NEW_REQ_HASH=$(git show "origin/$BRANCH:requirements.txt" 2>/dev/null | sha256sum | cut -d' ' -f1)

    c_info "Fetching latest code..."
    git fetch --progress origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
    c_ok "Repository updated to origin/$BRANCH"

    if [ "$OLD_REQ_HASH" != "$NEW_REQ_HASH" ]; then
        c_info "requirements.txt changed — dependencies will be upgraded in place"
    else
        c_info "requirements.txt unchanged — dependencies will be reused"
    fi

    # Restore the local customizations we backed up (so they survive the
    # reset). If the upstream update also touched one of those files, warn
    # the admin to review the new defaults against the backup.
    if [ -n "$BACKED_UP" ]; then
        for f in $BACKED_UP; do
            if [ -n "$OLD_HEAD" ] && git diff --quiet "$OLD_HEAD" HEAD -- "$f" 2>/dev/null; then
                : # upstream did NOT change this file — safe to restore as-is
            else
                c_info "Upstream also changed '$f' — review backup vs new defaults before trusting it"
            fi
            cp -a "$BACKUP_DIR/$f" "$f"
        done
        c_ok "Local customizations restored from $BACKUP_DIR"
    fi
else
    MODE="install"
    echo ""
    echo "  ╔══════════════════════════════════════╗"
    echo "  ║        CLEAN INSTALL MODE             ║"
    echo "  ╚══════════════════════════════════════╝"
    c_info "No existing install — running CLEAN INSTALL to $INSTALL_DIR"
    git clone --progress -b "$BRANCH" "$REPO" "$INSTALL_DIR"
    c_ok "Repository cloned"
    cd "$INSTALL_DIR"
fi

# --- 3. venv + deps (create once, upgrade in place — never rm a live venv) ---
if [ ! -d .venv ]; then
    c_info "Creating Python virtual environment..."
    python3 -m venv .venv
    c_ok "Virtual environment ready"
else
    c_info "Reusing existing virtual environment (.venv)"
fi

c_info "Installing / upgrading Python dependencies..."
.venv/bin/pip install --upgrade pip setuptools wheel
.venv/bin/pip install -r requirements.txt
touch .venv/installed.flag
c_ok "Python dependencies installed"

# --- verify yaml actually imports ---
if ! .venv/bin/python -c "import yaml" 2>/dev/null; then
    c_err "PyYAML failed to install — trying direct install..."
    .venv/bin/pip install PyYAML
    .venv/bin/python -c "import yaml" || { c_err "Cannot import yaml. Installation failed."; exit 1; }
fi
c_ok "Python dependencies installed (yaml verified)"

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
if [ "$MODE" = "update" ]; then
  TITLE="Update complete!"
else
  TITLE="Clean install complete!"
fi
echo "  ╔══════════════════════════════════════════════╗"
printf "  ║%-42s║\n" "  $TITLE"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
DEPLOYED=$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null)
DEPLOY_DATE=$(git -C "$INSTALL_DIR" show -s --format=%cs HEAD 2>/dev/null)
if [ -n "$DEPLOYED" ]; then
  echo "  Deployed:  $DEPLOY_DATE ($DEPLOYED)"
  echo ""
fi
if [ "$MODE" = "update" ]; then
  echo "  To run the new version:  systemctl restart huntproxy"
  echo ""
fi
if [ "$MODE" = "install" ]; then
  echo "  Service was NOT started automatically."
  echo ""
fi
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
echo "  Uninstall (removes service, firewall rules, cgroup, files):"
echo "    sudo $INSTALL_DIR/uninstall.sh"
echo ""
