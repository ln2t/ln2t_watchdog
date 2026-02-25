#!/usr/bin/env bash
# uninstall.sh – Remove ln2t_watchdog systemd units and Python package.
set -euo pipefail

echo "==> Stopping and disabling systemd timer …"
systemctl --user disable --now ln2t-watchdog.timer 2>/dev/null || true
systemctl --user stop ln2t-watchdog.service 2>/dev/null || true

UNIT_DIR="${HOME}/.config/systemd/user"
rm -f "$UNIT_DIR/ln2t-watchdog.service" "$UNIT_DIR/ln2t-watchdog.timer"
systemctl --user daemon-reload

echo "==> Uninstalling Python package …"
pip uninstall -y ln2t_watchdog 2>/dev/null || true

echo ""
echo "Done.  State files in ~/.local/state/ln2t_watchdog/ were NOT removed."
echo "Remove them manually if desired."
