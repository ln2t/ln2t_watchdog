#!/usr/bin/env bash
# install.sh – Install ln2t_watchdog and enable the systemd user timer.
#
# Usage:
#   ./install.sh          # install + enable timer
#
set -euo pipefail

# ============================================================================
# Color codes for output
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ============================================================================
# Helper functions
# ============================================================================

print_header() {
    echo -e "${BOLD}${GREEN}╔════════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║                         ln2t_watchdog installer                                 ║${NC}"
    echo -e "${BOLD}${GREEN}╚════════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    echo -e "${BOLD}${GREEN}==>${NC} ${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# ============================================================================
# Main installation
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

print_header

print_section "Installing ln2t_watchdog Python package"

# Detect if we're in a virtual environment
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    # Inside a venv: use pip install directly (no --user)
    print_info "Virtual environment detected: ${VIRTUAL_ENV}"
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org "$SCRIPT_DIR"
else
    # Outside a venv: use --user to install for current user
    print_info "Installing for current user (--user)"
    pip install --user --trusted-host pypi.org --trusted-host files.pythonhosted.org "$SCRIPT_DIR"
fi

print_success "Python package installed"

print_section "Installing systemd user units"

UNIT_DIR="${HOME}/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cp "$SCRIPT_DIR/systemd/ln2t-watchdog.service" "$UNIT_DIR/"
cp "$SCRIPT_DIR/systemd/ln2t-watchdog.timer"   "$UNIT_DIR/"

print_success "Systemd units copied to ${UNIT_DIR}"

print_section "Reloading systemd user daemon"

systemctl --user daemon-reload

print_success "Systemd daemon reloaded"

print_section "Enabling and starting ln2t-watchdog.timer"

systemctl --user enable --now ln2t-watchdog.timer

print_success "Timer enabled and started"

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}Installation complete!${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${BOLD}Next steps:${NC}"
echo ""
echo "  1. Verify installation:"
echo "     ${YELLOW}ln2t-watchdog --help${NC}"
echo ""
echo "  2. Check timer status:"
echo "     ${YELLOW}systemctl --user status ln2t-watchdog.timer${NC}"
echo ""
echo "  3. Generate a template configuration:"
echo "     ${YELLOW}ln2t-watchdog init -o my_config.yaml${NC}"
echo ""
echo "  4. Place configs in your dataset directories:"
echo "     ${YELLOW}~/code/YYYY-Adjective_Animal-randomString-code/ln2t_watchdog/*.yaml${NC}"
echo ""
echo "  5. Manually trigger a scan (optional):"
echo "     ${YELLOW}ln2t-watchdog run --dry-run${NC}    # preview"
echo "     ${YELLOW}ln2t-watchdog run${NC}              # execute"
echo ""
echo "  6. Monitor execution:"
echo "     ${YELLOW}ln2t-watchdog status${NC}"
echo "     ${YELLOW}ln2t-watchdog logs${NC}"
echo ""
