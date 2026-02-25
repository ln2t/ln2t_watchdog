#!/usr/bin/env bash
# uninstall.sh – Remove ln2t_watchdog systemd units and Python package.
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
    echo -e "${BOLD}${GREEN}║                         ln2t_watchdog uninstaller                              ║${NC}"
    echo -e "${BOLD}${GREEN}╚════════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    echo -e "${BOLD}${GREEN}==>${NC} ${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ============================================================================
# Main uninstallation
# ============================================================================

print_header

print_section "Stopping and disabling systemd timer"

systemctl --user disable --now ln2t-watchdog.timer 2>/dev/null || print_warning "Timer was not running"
systemctl --user stop ln2t-watchdog.service 2>/dev/null || true

print_success "Timer stopped and disabled"

print_section "Removing systemd units"

UNIT_DIR="${HOME}/.config/systemd/user"
rm -f "$UNIT_DIR/ln2t-watchdog.service" "$UNIT_DIR/ln2t-watchdog.timer"
systemctl --user daemon-reload

print_success "Systemd units removed"

print_section "Uninstalling Python package"

pip uninstall -y ln2t_watchdog 2>/dev/null || print_warning "Package was not installed"

print_success "Python package uninstalled"

echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}Uninstallation complete!${NC}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}Note:${NC} State files in ${BOLD}~/.local/state/ln2t_watchdog/${NC} were not removed."
echo "Remove them manually if needed:"
echo ""
echo "  ${YELLOW}rm -rf ~/.local/state/ln2t_watchdog${NC}"
echo ""
