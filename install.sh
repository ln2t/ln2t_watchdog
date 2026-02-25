#!/usr/bin/env bash
# install.sh – Install ln2t_watchdog and enable the systemd user timer.
#
# Usage:
#   ./install.sh          # install + enable timer
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing ln2t_watchdog Python package …"
pip install --user "$SCRIPT_DIR"

echo "==> Installing systemd user units …"
UNIT_DIR="${HOME}/.config/systemd/user"
mkdir -p "$UNIT_DIR"
cp "$SCRIPT_DIR/systemd/ln2t-watchdog.service" "$UNIT_DIR/"
cp "$SCRIPT_DIR/systemd/ln2t-watchdog.timer"   "$UNIT_DIR/"

echo "==> Reloading systemd user daemon …"
systemctl --user daemon-reload

echo "==> Enabling and starting ln2t-watchdog.timer …"
systemctl --user enable --now ln2t-watchdog.timer

echo ""
echo "Done!  Verify with:"
echo "  systemctl --user status ln2t-watchdog.timer"
echo "  ln2t-watchdog status"
echo ""
echo "To trigger a manual run:"
echo "  ln2t-watchdog run"
echo "  ln2t-watchdog run --dry-run   # preview only"
