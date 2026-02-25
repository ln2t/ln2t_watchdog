"""Status reporting for administrators."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ln2t_watchdog.runner import LAST_RUN_FILE, RUN_LOG_FILE, STATE_DIR
from ln2t_watchdog.scanner import DatasetConfig, scan_code_directory


def get_last_run_time() -> Optional[datetime]:
    """Return the timestamp of the last watchdog run, or *None*."""
    if not LAST_RUN_FILE.is_file():
        return None
    try:
        text = LAST_RUN_FILE.read_text().strip()
        return datetime.fromisoformat(text)
    except (ValueError, OSError):
        return None


def get_run_history(tail: int = 30) -> List[str]:
    """Return the last *tail* lines of the run-history log."""
    if not RUN_LOG_FILE.is_file():
        return []
    lines = RUN_LOG_FILE.read_text().splitlines()
    return lines[-tail:]


def get_recent_logs(dataset_dir: Path, limit: int = 10) -> List[Path]:
    """Return the most recent log files for a dataset, newest first."""
    log_dir = dataset_dir / "ln2t_watchdog" / "logs"
    if not log_dir.is_dir():
        return []
    logs = sorted(log_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[:limit]


def get_systemd_timer_status() -> str:
    """Query systemd for the ln2t-watchdog timer status (best-effort)."""
    import subprocess

    try:
        result = subprocess.run(
            ["systemctl", "--user", "status", "ln2t-watchdog.timer"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or result.stderr.strip()
    except FileNotFoundError:
        return "systemctl not available"
    except subprocess.TimeoutExpired:
        return "systemctl timed out"
    except Exception as exc:  # noqa: BLE001
        return f"Error querying systemctl: {exc}"


def format_status_report(code_dir: Path | None = None) -> str:
    """Build a human-readable status report."""
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("  ln2t_watchdog status report")
    lines.append("=" * 60)

    # Last run
    last_run = get_last_run_time()
    if last_run:
        lines.append(f"\nLast run: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        lines.append("\nLast run: never (or state file missing)")

    # Systemd timer
    lines.append(f"\n--- systemd timer ---")
    lines.append(get_systemd_timer_status())

    # Discovered datasets
    datasets = scan_code_directory(code_dir)
    lines.append(f"\n--- Discovered datasets ({len(datasets)}) ---")
    if not datasets:
        lines.append("  (none)")
    for ds in datasets:
        lines.append(f"  {ds.dataset_name}")
        for cf in ds.config_files:
            lines.append(f"    config: {cf.name}")

        recent = get_recent_logs(ds.dataset_dir, limit=5)
        if recent:
            lines.append(f"    recent logs:")
            for log_path in recent:
                size = log_path.stat().st_size
                mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
                lines.append(f"      {log_path.name}  ({size} bytes, {mtime:%Y-%m-%d %H:%M})")

    # Run history
    history = get_run_history(tail=20)
    if history:
        lines.append(f"\n--- Recent run history ---")
        for h in history:
            lines.append(f"  {h}")

    lines.append("")
    return "\n".join(lines)
