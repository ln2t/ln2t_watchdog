"""Status reporting for administrators."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ln2t_watchdog.runner import LAST_RUN_FILE, RUN_LOG_FILE, STATE_DIR
from ln2t_watchdog.scanner import DatasetConfig, scan_code_directory


# ANSI color codes matching cli.py
class _Colors:
    """ANSI color codes for terminal output."""
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def _format_header(title: str) -> str:
    """Format a colored header with box drawing."""
    width = 80
    # Create the box
    top = f"{_Colors.GREEN}╔{('═' * (width - 2))}╗{_Colors.END}"
    middle = f"{_Colors.GREEN}║{_Colors.END}  {_Colors.BOLD}{title:<{width - 6}}{_Colors.END}  {_Colors.GREEN}║{_Colors.END}"
    bottom = f"{_Colors.GREEN}╚{('═' * (width - 2))}╝{_Colors.END}"
    return f"{top}\n{middle}\n{bottom}"


def _format_section(title: str) -> str:
    """Format a colored section header."""
    return f"\n{_Colors.BOLD}{_Colors.CYAN}{title}{_Colors.END}"


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
    """Return the most recent log files for a dataset, newest first.
    
    Searches for logs in both ln2t_watchdog/logs and .ln2t_watchdog/logs directories.
    """
    logs: List[Path] = []
    
    # Check both regular and hidden config directories
    for config_dir in [dataset_dir / "ln2t_watchdog", dataset_dir / ".ln2t_watchdog"]:
        log_dir = config_dir / "logs"
        if log_dir.is_dir():
            logs.extend(log_dir.iterdir())
    
    if not logs:
        return []
    
    # Sort by modification time (newest first) and return top N
    logs_sorted = sorted(logs, key=lambda p: p.stat().st_mtime, reverse=True)
    return logs_sorted[:limit]


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
    
    # Timer status
    if timer_info["error"]:
        lines.append(f"  {_Colors.RED}✗{_Colors.END} Timer: ERROR – {timer_info['error']}")
    else:
        active_icon = f"{_Colors.GREEN}✓{_Colors.END}" if timer_info["active"] == "active" else f"{_Colors.RED}✗{_Colors.END}"
        enabled_icon = f"{_Colors.GREEN}✓{_Colors.END}" if timer_info["enabled"] == "enabled" else "○"
        lines.append(
            f"  {active_icon} Timer: {_Colors.YELLOW}active{_Colors.END}={timer_info['active']}, "
            f"{enabled_icon} {_Colors.YELLOW}enabled{_Colors.END}={timer_info['enabled']}"
        )
    
    # Service status
    if service_info["error"]:
        lines.append(f"  {_Colors.RED}✗{_Colors.END} Service: ERROR – {service_info['error']}")
    else:
        active_icon = f"{_Colors.GREEN}✓{_Colors.END}" if service_info["active"] == "active" else "○"
        enabled_icon = f"{_Colors.GREEN}✓{_Colors.END}" if service_info["enabled"] == "enabled" else "○"
        lines.append(
            f"  {active_icon} Service: {_Colors.YELLOW}active{_Colors.END}={service_info['active']}, "
            f"{enabled_icon} {_Colors.YELLOW}enabled{_Colors.END}={service_info['enabled']}"
        )
    
    return "\n".join(lines)


def format_status_report(code_dir: Path | None = None) -> str:
    """Build a human-readable status report."""
    lines: List[str] = []
    
    lines.append(_format_header("ln2t_watchdog status report"))
    
    # Last run
    last_run = get_last_run_time()
    if last_run:
        lines.append(f"\n{_Colors.BOLD}Last run:{_Colors.END} {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        lines.append(f"\n{_Colors.BOLD}Last run:{_Colors.END} never (or state file missing)")

    # Systemd status
    lines.append(_format_section("systemd status"))
    lines.append(get_systemd_status_summary())

    # Discovered datasets
    datasets = scan_code_directory(code_dir)
    lines.append(_format_section(f"Discovered datasets ({len(datasets)})"))
    if not datasets:
        lines.append("  (none)")
    else:
        for ds in datasets:
            lines.append(f"  {_Colors.CYAN}{ds.dataset_name}{_Colors.END}")
            for cf in ds.config_files:
                lines.append(f"    {_Colors.YELLOW}config:{_Colors.END} {cf.name}")

            recent = get_recent_logs(ds.dataset_dir, limit=5)
            if recent:
                lines.append(f"    {_Colors.YELLOW}recent logs:{_Colors.END}")
                for log_path in recent:
                    size = log_path.stat().st_size
                    mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
                    lines.append(f"      {log_path.name}  ({size} bytes, {mtime:%Y-%m-%d %H:%M})")

    # Run history
    history = get_run_history(tail=20)
    if history:
        lines.append(_format_section("Recent run history"))
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
    
    lines.append(_format_header("Running watchdog jobs"))
    
    if not jobs:
        lines.append("\nNo running jobs found.")
    else:
        lines.append(f"\n{_Colors.BOLD}Total:{_Colors.END} {len(jobs)} job(s)")
        lines.append("")
        lines.append(f"  {_Colors.BOLD}{'PID':<10} {'Dataset':<25} {'Tool':<20}{_Colors.END}")
        lines.append(f"  {_Colors.CYAN}{'-' * 78}{_Colors.END}")
        
        for pid, dataset, tool, ts in sorted(jobs):
            lines.append(f"  {pid:<10} {dataset:<25} {tool:<20}")
    
    lines.append("")
    return "\n".join(lines)
