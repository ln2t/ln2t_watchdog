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


def check_systemd_unit(unit_name: str) -> dict:
    """Check detailed status of a systemd user unit.
    
    Returns a dict with keys:
    - 'exists': bool - whether the unit exists
    - 'active': str - active state (active, inactive, etc.)
    - 'enabled': str - enabled state (enabled, disabled, etc.)
    - 'status': str - full status output
    - 'error': str - error message if any
    """
    import subprocess
    
    result = {
        "exists": False,
        "active": "unknown",
        "enabled": "unknown",
        "status": "",
        "error": None,
    }
    
    try:
        # Check if unit exists
        check_result = subprocess.run(
            ["systemctl", "--user", "list-units", unit_name, "-q"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        result["exists"] = check_result.returncode == 0
        
        # Get full status
        status_result = subprocess.run(
            ["systemctl", "--user", "status", unit_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        result["status"] = status_result.stdout.strip() or status_result.stderr.strip()
        
        # Extract active state
        is_active_result = subprocess.run(
            ["systemctl", "--user", "is-active", unit_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        result["active"] = is_active_result.stdout.strip()
        
        # Extract enabled state
        is_enabled_result = subprocess.run(
            ["systemctl", "--user", "is-enabled", unit_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        result["enabled"] = is_enabled_result.stdout.strip()
        
    except FileNotFoundError:
        result["error"] = "systemctl not available"
    except subprocess.TimeoutExpired:
        result["error"] = "systemctl timed out"
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    
    return result


def get_systemd_service_status() -> str:
    """Query systemd for the ln2t-watchdog service status (best-effort)."""
    import subprocess

    try:
        result = subprocess.run(
            ["systemctl", "--user", "status", "ln2t-watchdog.service"],
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


def get_systemd_status_summary() -> str:
    """Get a concise summary of systemd unit status.
    
    Returns a formatted string showing whether timer and service are active/enabled.
    """
    lines: List[str] = []
    
    timer_info = check_systemd_unit("ln2t-watchdog.timer")
    service_info = check_systemd_unit("ln2t-watchdog.service")
    
    lines.append("systemd units:")
    
    # Timer status
    if timer_info["error"]:
        lines.append(f"  Timer: ERROR – {timer_info['error']}")
    else:
        active_icon = "✓" if timer_info["active"] == "active" else "✗"
        enabled_icon = "✓" if timer_info["enabled"] == "enabled" else "○"
        lines.append(
            f"  Timer:  {active_icon} active={timer_info['active']}, "
            f"{enabled_icon} enabled={timer_info['enabled']}"
        )
    
    # Service status
    if service_info["error"]:
        lines.append(f"  Service: ERROR – {service_info['error']}")
    else:
        active_icon = "✓" if service_info["active"] == "active" else "○"
        enabled_icon = "✓" if service_info["enabled"] == "enabled" else "○"
        lines.append(
            f"  Service: {active_icon} active={service_info['active']}, "
            f"{enabled_icon} enabled={service_info['enabled']}"
        )
    
    return "\n".join(lines)


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

    # Systemd status
    lines.append(f"\n--- systemd status ---")
    lines.append(get_systemd_status_summary())

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


def get_running_jobs() -> List[Tuple[int, str, str, str]]:
    """Parse run history log and return all running jobs.
    
    Returns a list of tuples: (pid, dataset_name, tool_name, timestamp)
    Only includes jobs that are still alive (verified via /proc or kill check).
    """
    import re
    import signal
    
    if not RUN_LOG_FILE.is_file():
        return []
    
    running: List[Tuple[int, str, str, str]] = []
    
    # Parse all STARTED entries from the run history
    for line in RUN_LOG_FILE.read_text().splitlines():
        # Expected format: ISO_TIMESTAMP  dataset_name  tool_name  STARTED (PID xxxxx)
        if "STARTED (PID " not in line:
            continue
        
        # Extract the PID from the status string
        match = re.search(r"STARTED \(PID (\d+)\)", line)
        if not match:
            continue
        
        pid = int(match.group(1))
        parts = line.split(None, 3)  # Split on whitespace, max 4 parts
        
        if len(parts) < 4:
            continue
        
        # parts[0] is timestamp (YYYYMMDD_HHMMSS format in the log)
        timestamp_str = parts[0]
        dataset_name = parts[1]
        tool_name = parts[2]
        
        # Check if process still exists
        try:
            os.kill(pid, 0)  # Signal 0 just checks existence
            running.append((pid, dataset_name, tool_name, timestamp_str))
        except ProcessLookupError:
            # Process is dead, skip it
            pass
        except PermissionError:
            # Permission denied means process exists and is owned by another user
            running.append((pid, dataset_name, tool_name, timestamp_str))
        except OSError:
            # Other error, skip
            pass
    
    return running


def format_jobs_report(jobs: List[Tuple[int, str, str, str]] | None = None) -> str:
    """Format a report of running jobs.
    
    If jobs is None, fetches current running jobs.
    """
    if jobs is None:
        jobs = get_running_jobs()
    
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("  Running watchdog jobs")
    lines.append("=" * 80)
    
    if not jobs:
        lines.append("\nNo running jobs found.")
    else:
        lines.append(f"\nTotal: {len(jobs)} job(s)")
        lines.append("")
        lines.append(f"{'PID':<10} {'Dataset':<30} {'Tool':<20}")
        lines.append("-" * 80)
        
        for pid, dataset, tool, ts in sorted(jobs):
            lines.append(f"{pid:<10} {dataset:<30} {tool:<20}")
    
    lines.append("")
    return "\n".join(lines)
