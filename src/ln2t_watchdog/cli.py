"""Command-line interface for ln2t_watchdog."""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from pathlib import Path

from ln2t_watchdog import __version__
from ln2t_watchdog.parser import parse_config_file
from ln2t_watchdog.runner import record_run_start, run_all
from ln2t_watchdog.scanner import scan_code_directory
from ln2t_watchdog.status import format_status_report

logger = logging.getLogger("ln2t_watchdog")


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


class ColoredHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter with colored section headers."""

    def __init__(self, prog, indent_increment=2, max_help_position=40, width=100):
        super().__init__(prog, indent_increment, max_help_position, width)

    def _format_usage(self, usage, actions, groups, prefix):
        if prefix is None:
            prefix = f"{Colors.BOLD}Usage:{Colors.END} "
        return super()._format_usage(usage, actions, groups, prefix)

    def start_section(self, heading):
        if heading:
            heading = f"{Colors.BOLD}{Colors.CYAN}{heading}{Colors.END}"
        super().start_section(heading)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.setLevel(level)
    logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Scan for configs and launch all discovered tool commands."""
    code_dir = Path(args.code_dir).expanduser() if args.code_dir else None
    datasets = scan_code_directory(code_dir)

    if not datasets:
        logger.info("No datasets with ln2t_watchdog configs found.")
        return

    record_run_start()

    total_launched = 0
    for ds in datasets:
        for config_file in ds.config_files:
            specs = parse_config_file(config_file, ds.dataset_name)
            if not specs:
                logger.warning("No tool specs parsed from %s", config_file)
                continue
            pids = run_all(specs, ds.dataset_dir, dry_run=args.dry_run)
            total_launched += sum(1 for p in pids if p is not None or args.dry_run)

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    logger.info("[%s] Finished – %d command(s) dispatched.", mode, total_launched)


def cmd_list(args: argparse.Namespace) -> None:
    """List discovered datasets and their configs."""
    code_dir = Path(args.code_dir).expanduser() if args.code_dir else None
    datasets = scan_code_directory(code_dir)

    if not datasets:
        print("No datasets with ln2t_watchdog configs found.")
        return

    for ds in datasets:
        print(f"\n{ds.dataset_name}")
        for cf in ds.config_files:
            print(f"  config: {cf}")
            specs = parse_config_file(cf, ds.dataset_name)
            for spec in specs:
                print(f"    -> {spec.build_command_string()}")


def cmd_status(args: argparse.Namespace) -> None:
    """Print a status report."""
    code_dir = Path(args.code_dir).expanduser() if args.code_dir else None
    print(format_status_report(code_dir))


def cmd_logs(args: argparse.Namespace) -> None:
    """Show recent log files for a dataset."""
    code_dir = Path(args.code_dir).expanduser() if args.code_dir else None
    datasets = scan_code_directory(code_dir)

    target = args.dataset
    for ds in datasets:
        if target and ds.dataset_name != target:
            continue
        log_dir = ds.dataset_dir / "ln2t_watchdog" / "logs"
        if not log_dir.is_dir():
            print(f"  No logs for {ds.dataset_name}")
            continue
        print(f"\nLogs for {ds.dataset_name}:")
        logs = sorted(log_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for lf in logs[: args.limit]:
            size = lf.stat().st_size
            print(f"  {lf.name}  ({size} bytes)")
        if not logs:
            print("  (none)")


def cmd_init(args: argparse.Namespace) -> None:
    """Generate a template configuration file."""
    output_path = Path(args.output).expanduser()

    template = """\
# ln2t_watchdog configuration template
#
# Edit this file to specify which ln2t_tools pipelines to run and their settings.
# Place it in: ~/code/<dataset>-code/ln2t_watchdog/<name>.yaml

ln2t_tools:
  # Example: freesurfer pipeline
  # freesurfer:
  #   version: "7.2.0"
  #   tool_args: "--recon-all all"
  #   participant-label:
  #     - "001"
  #     - "042"
  #     - "666"
  #
  # Example: fmriprep pipeline
  # fmriprep:
  #   version: "21.1.4"
  #   tool_args: "--fs-noreconall"
  #   participant-label:
  #     - "001"
  #     - "042"
"""

    try:
        output_path.write_text(template)
        print(f"Template created: {output_path}")
        print(f"Edit this file and place it in: ~/code/<dataset>-code/ln2t_watchdog/")
    except OSError as exc:
        logger.error("Failed to write template: %s", exc)
        sys.exit(1)


def cmd_systemctl(args: argparse.Namespace) -> None:
    """Check systemd timer and service status."""
    from ln2t_watchdog.status import (
        check_systemd_unit,
        get_systemd_status_summary,
        get_systemd_timer_status,
        get_systemd_service_status,
    )

    print()
    print("=" * 72)
    print("  ln2t_watchdog systemd status")
    print("=" * 72)
    print()

    # Show summary
    print(get_systemd_status_summary())
    print()

    if args.detailed:
        print("-" * 72)
        print("  Timer details")
        print("-" * 72)
        print(get_systemd_timer_status())
        print()

        print("-" * 72)
        print("  Service details")
        print("-" * 72)
        print(get_systemd_service_status())
        print()


def cmd_jobs(args: argparse.Namespace) -> None:
    """List all running watchdog jobs."""
    from ln2t_watchdog.status import format_jobs_report
    
    print()
    print(format_jobs_report())


def cmd_kill(args: argparse.Namespace) -> None:
    """Kill one or more running watchdog jobs."""
    from ln2t_watchdog.runner import kill_process_group, force_kill_process_group
    from ln2t_watchdog.status import get_running_jobs
    
    jobs = get_running_jobs()
    
    if not jobs:
        print("No running watchdog jobs found.")
        return
    
    # Determine which jobs to kill
    jobs_to_kill = []
    
    if args.pid:
        # Kill specific PID
        pid = args.pid
        matching = [j for j in jobs if j[0] == pid]
        if not matching:
            print(f"PID {pid} is not a running watchdog job.")
            return
        jobs_to_kill = matching
    
    elif args.job:
        # Kill all jobs for a specific tool (or dataset.tool)
        job_spec = args.job
        if "." in job_spec:
            # Format: dataset.tool
            dataset, tool = job_spec.split(".", 1)
            matching = [j for j in jobs if j[1] == dataset and j[2] == tool]
        else:
            # Just tool name - kill all instances  
            matching = [j for j in jobs if j[2] == job_spec]
        
        if not matching:
            print(f"No running jobs matching '{job_spec}'.")
            return
        jobs_to_kill = matching
    
    elif args.dataset:
        # Kill all jobs for a specific dataset
        dataset = args.dataset
        matching = [j for j in jobs if j[1] == dataset]
        if not matching:
            print(f"No running jobs for dataset '{dataset}'.")
            return
        jobs_to_kill = matching
    
    elif args.all:
        # Kill all running jobs
        jobs_to_kill = jobs
    
    else:
        print("No target specified. Use --pid, --job, --dataset, or --all.")
        print("Run 'ln2t-watchdog jobs' to see running jobs.")
        return
    
    if not jobs_to_kill:
        print("No matching jobs to kill.")
        return
    
    # Confirm if killing multiple jobs
    if len(jobs_to_kill) > 1:
        print(f"\nAbout to kill {len(jobs_to_kill)} job(s):")
        for pid, dataset, tool, ts in sorted(jobs_to_kill):
            print(f"  PID {pid}: {dataset}/{tool}")
        
        if not args.force:
            response = input("\nProceed? (y/N): ").strip().lower()
            if response != "y":
                print("Cancelled.")
                return
    
    # Kill the jobs
    print()
    for pid, dataset, tool, ts in sorted(jobs_to_kill):
        if args.force:
            success, msg = force_kill_process_group(pid)
        else:
            success, msg = kill_process_group(pid)
        
        status_icon = "✓" if success else "✗"
        print(f"  {status_icon} {msg}")
    
    print()


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""

    description = textwrap.dedent(
        f"""
    {Colors.BOLD}{Colors.GREEN}╔════════════════════════════════════════════════════════════════════════════════╗
    ║                      ln2t_watchdog v{__version__:<56}║
    ║              Automated nightly data-processing scheduler                   ║
    ╚════════════════════════════════════════════════════════════════════════════════╝{Colors.END}

    {Colors.BOLD}Description:{Colors.END}
      ln2t_watchdog scans dataset directories for processing configurations,
      builds ln2t_tools commands, and launches them in the background with
      full logging. Runs automatically every night via systemd timer.

    {Colors.BOLD}Setup:{Colors.END}
      1. Create folders in ~/code/YYYY-Adjective_Animal-randomString-code/ln2t_watchdog/
      2. Place YAML configuration files there
      3. Enable the systemd timer via install.sh
    """
    )

    epilog = textwrap.dedent(
        f"""
    {Colors.BOLD}{Colors.GREEN}════════════════════════════════════════════════════════════════════════════════{Colors.END}
    {Colors.BOLD}EXAMPLES{Colors.END}
    {Colors.GREEN}════════════════════════════════════════════════════════════════════════════════{Colors.END}

    {Colors.BOLD}Generate a template configuration file:{Colors.END}

      {Colors.YELLOW}# Create template in current directory{Colors.END}
      ln2t-watchdog init

      {Colors.YELLOW}# Create template at custom location{Colors.END}
      ln2t-watchdog init -o ~/my_pipelines.yaml

    {Colors.BOLD}Discover and configure:{Colors.END}

      {Colors.YELLOW}# List all discovered datasets and configured pipelines{Colors.END}
      ln2t-watchdog list

      {Colors.YELLOW}# Preview what would be executed (dry-run){Colors.END}
      ln2t-watchdog run --dry-run

    {Colors.BOLD}Manual execution and monitoring:{Colors.END}

      {Colors.YELLOW}# Manually trigger a scan and launch all pipelines{Colors.END}
      ln2t-watchdog run

      {Colors.YELLOW}# Show watchdog status with last run time and recent logs{Colors.END}
      ln2t-watchdog status

      {Colors.YELLOW}# View recent execution logs{Colors.END}
      ln2t-watchdog logs

      {Colors.YELLOW}# View logs for a specific dataset{Colors.END}
      ln2t-watchdog logs 2024-Happy_Dog-abc123

    {Colors.BOLD}Advanced monitoring:{Colors.END}

      {Colors.YELLOW}# Check systemd timer and service status{Colors.END}
      ln2t-watchdog systemctl

      {Colors.YELLOW}# Show detailed systemd status{Colors.END}
      ln2t-watchdog systemctl --detailed

      {Colors.YELLOW}# Verbose output with debug logging{Colors.END}
      ln2t-watchdog -v run

      {Colors.YELLOW}# Override code directory{Colors.END}
      ln2t-watchdog --code-dir /custom/path list

    {Colors.BOLD}{Colors.GREEN}════════════════════════════════════════════════════════════════════════════════{Colors.END}
    {Colors.BOLD}CONFIGURATION FILE FORMAT{Colors.END}
    {Colors.GREEN}════════════════════════════════════════════════════════════════════════════════{Colors.END}

    Location: {Colors.CYAN}~/code/<dataset>-code/ln2t_watchdog/*.yaml{Colors.END}

    Example:
      ln2t_tools:
        freesurfer:
          version: "7.2.0"
          tool_args: "--recon-all all"
          participant-label:
            - "001"
            - "042"

    {Colors.BOLD}Note:{Colors.END} All fields (version, tool_args, participant-label)
    are optional and will be omitted if not specified.

    {Colors.BOLD}{Colors.GREEN}════════════════════════════════════════════════════════════════════════════════{Colors.END}
    {Colors.BOLD}MORE INFORMATION{Colors.END}
    {Colors.GREEN}════════════════════════════════════════════════════════════════════════════════{Colors.END}

      Documentation:  https://github.com/ln2t/ln2t_watchdog
      Report Issues:  https://github.com/ln2t/ln2t_watchdog/issues
      Version:        {__version__}
    """
    )

    parser = argparse.ArgumentParser(
        prog="ln2t-watchdog",
        description=description,
        epilog=epilog,
        formatter_class=ColoredHelpFormatter,
        add_help=False,
    )

    # =========================================================================
    # GENERAL OPTIONS
    # =========================================================================
    general = parser.add_argument_group(f"{Colors.BOLD}General Options{Colors.END}")

    general.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit.",
    )

    general.add_argument(
        "--version",
        action="version",
        version=f"ln2t-watchdog {__version__}",
        help="Show program version and exit.",
    )

    general.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output (DEBUG level logging).",
    )

    general.add_argument(
        "--code-dir",
        default=None,
        metavar="PATH",
        help="Override the code directory (default: ~/code).",
    )

    # =========================================================================
    # SUBCOMMANDS
    # =========================================================================
    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    p_run = sub.add_parser(
        "run",
        help="Scan configurations and launch tool commands.",
        formatter_class=ColoredHelpFormatter,
    )
    p_run.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )

    # --- list ---
    sub.add_parser(
        "list",
        help="List discovered datasets and their configured pipelines.",
        formatter_class=ColoredHelpFormatter,
    )

    # --- status ---
    sub.add_parser(
        "status",
        help="Show watchdog status report (timer, last run, logs).",
        formatter_class=ColoredHelpFormatter,
    )

    # --- logs ---
    p_logs = sub.add_parser(
        "logs",
        help="Show recent log files for monitored datasets.",
        formatter_class=ColoredHelpFormatter,
    )
    p_logs.add_argument(
        "dataset",
        nargs="?",
        default=None,
        help="Filter by dataset name (optional).",
    )
    p_logs.add_argument(
        "-l",
        "--limit",
        type=int,
        default=20,
        metavar="N",
        help="Maximum number of log files to show (default: 20).",
    )

    # --- init ---
    p_init = sub.add_parser(
        "init",
        help="Generate a template configuration file.",
        formatter_class=ColoredHelpFormatter,
    )
    p_init.add_argument(
        "-o",
        "--output",
        default="ln2t_watchdog_config.yaml",
        metavar="FILE",
        help="Output file path (default: ln2t_watchdog_config.yaml).",
    )

    # --- systemctl ---
    p_systemctl = sub.add_parser(
        "systemctl",
        help="Check systemd timer and service status.",
        formatter_class=ColoredHelpFormatter,
    )
    p_systemctl.add_argument(
        "-d",
        "--detailed",
        action="store_true",
        help="Show detailed status output from systemctl.",
    )

    # --- jobs ---
    sub.add_parser(
        "jobs",
        help="List all running watchdog jobs.",
        formatter_class=ColoredHelpFormatter,
    )

    # --- kill ---
    p_kill = sub.add_parser(
        "kill",
        help="Kill one or more running watchdog jobs.",
        formatter_class=ColoredHelpFormatter,
    )
    kill_group = p_kill.add_mutually_exclusive_group()
    kill_group.add_argument(
        "--pid",
        type=int,
        metavar="PID",
        help="Kill a specific job by PID.",
    )
    kill_group.add_argument(
        "--job",
        metavar="TOOL",
        help="Kill all jobs for a specific tool (use format 'dataset.tool' for specificity).",
    )
    kill_group.add_argument(
        "--dataset",
        metavar="DATASET",
        help="Kill all jobs for a specific dataset.",
    )
    kill_group.add_argument(
        "--all",
        action="store_true",
        help="Kill all running watchdog jobs.",
    )
    p_kill.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Send SIGKILL instead of SIGTERM, and skip confirmation prompts.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = create_parser()
    args = parser.parse_args(argv)
    _setup_logging(verbose=args.verbose)

    dispatch = {
        "run": cmd_run,
        "list": cmd_list,
        "status": cmd_status,
        "logs": cmd_logs,
        "init": cmd_init,
        "systemctl": cmd_systemctl,
        "jobs": cmd_jobs,
        "kill": cmd_kill,
    }
    dispatch[args.command](args)

