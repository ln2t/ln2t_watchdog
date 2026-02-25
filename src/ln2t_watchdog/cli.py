"""Command-line interface for ln2t_watchdog."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ln2t_watchdog import __version__
from ln2t_watchdog.parser import parse_config_file
from ln2t_watchdog.runner import record_run_start, run_all
from ln2t_watchdog.scanner import scan_code_directory
from ln2t_watchdog.status import format_status_report

logger = logging.getLogger("ln2t_watchdog")


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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ln2t-watchdog",
        description="Automated nightly scheduler for ln2t_tools pipelines.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    parser.add_argument(
        "--code-dir",
        default=None,
        help="Override the code directory (default: ~/code).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- run ---
    p_run = sub.add_parser("run", help="Scan configs and launch tool commands.")
    p_run.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )

    # --- list ---
    sub.add_parser("list", help="List discovered datasets and commands.")

    # --- status ---
    sub.add_parser("status", help="Show watchdog status report.")

    # --- logs ---
    p_logs = sub.add_parser("logs", help="Show recent log files.")
    p_logs.add_argument("dataset", nargs="?", default=None, help="Filter by dataset name.")
    p_logs.add_argument("-l", "--limit", type=int, default=20, help="Max log files to show.")

    # --- init ---
    p_init = sub.add_parser("init", help="Generate a template configuration file.")
    p_init.add_argument(
        "-o",
        "--output",
        default="ln2t_watchdog_config.yaml",
        help="Output file path (default: ln2t_watchdog_config.yaml).",
    )

    args = parser.parse_args(argv)
    _setup_logging(verbose=args.verbose)

    dispatch = {
        "run": cmd_run,
        "list": cmd_list,
        "status": cmd_status,
        "logs": cmd_logs,
        "init": cmd_init,
    }
    dispatch[args.command](args)
