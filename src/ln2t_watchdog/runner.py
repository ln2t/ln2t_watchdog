"""Execute ln2t_tools commands in the background with logging."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ln2t_watchdog.parser import ToolSpec

logger = logging.getLogger(__name__)

# Shared state directory for run metadata
STATE_DIR = Path.home() / ".local" / "state" / "ln2t_watchdog"
LAST_RUN_FILE = STATE_DIR / "last_run"
RUN_LOG_FILE = STATE_DIR / "run_history.log"


def ensure_state_dir() -> None:
    """Create the state directory if it does not exist."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def log_dir_for_dataset(dataset_dir: Path) -> Path:
    """Return (and create) the log directory for a dataset."""
    log_dir = dataset_dir / "ln2t_watchdog" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _log_path(log_dir: Path, tool_name: str, timestamp: str, stream: str) -> Path:
    """Build a log file path: ``<tool>_<timestamp>_<stream>.log``."""
    return log_dir / f"{tool_name}_{timestamp}_{stream}.log"


def run_tool(spec: ToolSpec, dataset_dir: Path, dry_run: bool = False) -> Optional[int]:
    """Launch a single tool command.

    * stdout  → ``<logs>/<tool>_<ts>_stdout.log``
    * stderr  → ``<logs>/<tool>_<ts>_stderr.log``

    Returns the PID of the background process (or *None* in dry-run mode).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = log_dir_for_dataset(dataset_dir)

    stdout_path = _log_path(log_dir, spec.tool_name, timestamp, "stdout")
    stderr_path = _log_path(log_dir, spec.tool_name, timestamp, "stderr")

    cmd = spec.build_command()
    cmd_str = spec.build_command_string()

    if dry_run:
        logger.info("[DRY-RUN] %s", cmd_str)
        print(f"[DRY-RUN] {cmd_str}")
        return None

    logger.info("Launching: %s", cmd_str)
    logger.info("  stdout → %s", stdout_path)
    logger.info("  stderr → %s", stderr_path)

    try:
        with open(stdout_path, "w") as f_out, open(stderr_path, "w") as f_err:
            proc = subprocess.Popen(
                cmd,
                stdout=f_out,
                stderr=f_err,
                start_new_session=True,  # detach from parent process group
            )
    except FileNotFoundError:
        logger.error("Command not found: %s", cmd[0])
        _record_run(spec, "FAILED (command not found)", timestamp)
        return None
    except OSError as exc:
        logger.error("Failed to start command: %s", exc)
        _record_run(spec, f"FAILED ({exc})", timestamp)
        return None

    logger.info("  PID: %d", proc.pid)
    _record_run(spec, f"STARTED (PID {proc.pid})", timestamp)
    return proc.pid


def run_all(
    specs: List[ToolSpec],
    dataset_dir: Path,
    dry_run: bool = False,
) -> List[Optional[int]]:
    """Run every tool specification, returning a list of PIDs."""
    pids: List[Optional[int]] = []
    for spec in specs:
        pid = run_tool(spec, dataset_dir, dry_run=dry_run)
        pids.append(pid)
    return pids


def _record_run(spec: ToolSpec, status: str, timestamp: str) -> None:
    """Append a line to the run-history log and update last-run marker."""
    ensure_state_dir()
    line = f"{timestamp}  {spec.dataset_name}  {spec.tool_name}  {status}\n"
    with open(RUN_LOG_FILE, "a") as fh:
        fh.write(line)
    LAST_RUN_FILE.write_text(datetime.now().isoformat() + "\n")


def record_run_start() -> None:
    """Mark the beginning of a watchdog run cycle."""
    ensure_state_dir()
    LAST_RUN_FILE.write_text(datetime.now().isoformat() + "\n")
    with open(RUN_LOG_FILE, "a") as fh:
        fh.write(f"\n{'='*60}\n")
        fh.write(f"Watchdog run started at {datetime.now().isoformat()}\n")
        fh.write(f"{'='*60}\n")


def kill_process_group(pid: int) -> tuple[bool, str]:
    """Kill a process and its entire process group.
    
    Since jobs are launched with start_new_session=True, they form their own
    process group. This function kills the entire group.
    
    Returns a tuple of (success: bool, message: str).
    """
    try:
        # Get the process group ID (should be the PID itself since we used start_new_session)
        pgid = os.getpgid(pid)
        
        # Try to check if process exists first
        try:
            os.kill(pid, 0)  # Signal 0 just checks if PID exists
        except ProcessLookupError:
            return False, f"Process {pid} not found (already terminated?)"
        
        # Kill the entire process group with SIGTERM
        os.killpg(pgid, signal.SIGTERM)
        logger.info("Sent SIGTERM to process group %d (leader PID %d)", pgid, pid)
        
        return True, f"Terminated process group {pgid} (PID {pid})"
    except ProcessLookupError:
        return False, f"Process {pid} not found"
    except PermissionError:
        return False, f"Permission denied to kill PID {pid}"
    except OSError as exc:
        return False, f"Failed to kill PID {pid}: {exc}"


def force_kill_process_group(pid: int) -> tuple[bool, str]:
    """Force kill a process group with SIGKILL.
    
    This is more forceful than kill_process_group and should be used
    after SIGTERM has been ignored.
    
    Returns a tuple of (success: bool, message: str).
    """
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGKILL)
        logger.info("Sent SIGKILL to process group %d (leader PID %d)", pgid, pid)
        return True, f"Force-killed process group {pgid} (PID {pid})"
    except ProcessLookupError:
        return False, f"Process {pid} not found"
    except PermissionError:
        return False, f"Permission denied to kill PID {pid}"
    except OSError as exc:
        return False, f"Failed to force-kill PID {pid}: {exc}"
