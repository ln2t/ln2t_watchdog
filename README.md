# ln2t_watchdog

Automated nightly data-processing scheduler for **ln2t_tools** pipelines.

`ln2t_watchdog` scans `~/code/` for dataset directories matching the pattern
`YYYY-Adjective_Animal-randomString-code`, reads YAML configuration files in
each dataset's `ln2t_watchdog/` subfolder, builds the corresponding
`ln2t_tools` commands, and launches them in the background with full logging.

A **systemd user timer** triggers the scan every night at 02:00.

---

## Quick start

`ln2t_watchdog` is a Python package that installs a CLI tool and systemd user timer.

**Recommended: Use a dedicated Python virtual environment:**

```bash
# Create a venv
python3 -m venv ~/.venv/ln2t_watchdog
source ~/.venv/ln2t_watchdog/bin/activate

# Install
./install.sh
```

Alternatively, install globally with `--user`:

```bash
./install.sh
```

## Uninstall

```bash
./uninstall.sh
```

---

## Directory layout

```
~/code/
└── 2024-Happy_Dog-abc123-code/        # dataset code directory
    └── ln2t_watchdog/                 # configuration folder (or .ln2t_watchdog for hidden)
        ├── my_pipelines.yaml           # configuration file(s)
        └── logs/                        # created automatically
            ├── freesurfer_20260225_020012_stdout.log
            ├── freesurfer_20260225_020012_stderr.log
            └── …
```

## Configuration file format

Place one or more `.yaml` files in `~/code/<dataset>-code/ln2t_watchdog/` or `~/.ln2t_watchdog/` (hidden folder for privacy).

```yaml
ln2t_tools:
  freesurfer:
    version: "7.2.0"
    tool_args: "--recon-all all"
    participant-label:
      - "001"
      - "042"
      - "666"

  fmriprep:
    version: "21.1.4"
    tool_args: "--fs-noreconall"
    participant-label:
      - "001"
      - "042"
      - "666"
```

All fields under a tool name (`version`, `tool_args`, `participant-label`) are
**optional**.  If absent they are simply omitted from the generated command.

The above produces these commands:

```
ln2t_tools freesurfer --dataset 2024-Happy_Dog-abc123 --version 7.2.0 --tool-args "--recon-all all" --participant-label 001 042 666
ln2t_tools fmriprep   --dataset 2024-Happy_Dog-abc123 --version 21.1.4 --tool-args "--fs-noreconall" --participant-label 001 042 666
```

---

## CLI reference

```
ln2t-watchdog [--code-dir DIR] [-v] <command>
```

| Command   | Description |
|-----------|-------------|
| `run`     | Scan all configs and launch commands. **Prevents duplicate jobs** — skips launching if the same tool is already running on the same dataset. Options: `-n` / `--dry-run` to preview; `--dataset NAME` to run only for a specific dataset; `--force` to bypass duplicate prevention. |
| `list`    | List discovered datasets and the commands that would be generated. |
| `status`  | Print a status report (last run, systemd timer state, recent logs). |
| `logs`    | Show recent log files, optionally filtered by dataset name. |
| `clean-logfiles` | Delete old log files, keeping only the most recent one per dataset. Options: `--dataset NAME` to clean only that dataset (default: all); `-f` / `--force` to skip confirmation prompt. |
| `init`    | Generate a template configuration file. |

### Examples

```bash
# Generate a template config file
ln2t-watchdog init -o my_pipelines.yaml

# Preview what would run
ln2t-watchdog run --dry-run

# Actually launch everything (with duplicate prevention)
ln2t-watchdog run

# Run only for a specific dataset
ln2t-watchdog run --dataset 2024-Happy_Dog-abc123

# Force launch even if jobs are already running (bypasses duplicate prevention)
ln2t-watchdog run --force

# Show status
ln2t-watchdog status

# List all discovered pipelines
ln2t-watchdog list

# Show logs for a specific dataset
ln2t-watchdog logs 2024-Happy_Dog-abc123

# Clean up old log files (keep only the most recent per dataset)
ln2t-watchdog clean-logfiles        # Clean all datasets with confirmation
ln2t-watchdog clean-logfiles --force # Clean without confirmation
ln2t-watchdog clean-logfiles --dataset 2024-Happy_Dog-abc123  # Clean only one dataset

# View and manage running jobs
ln2t-watchdog jobs              # List all running jobs
ln2t-watchdog kill --all        # Terminate all running jobs
ln2t-watchdog kill --pid 12345  # Terminate job with specific PID
```

---

## systemd integration

The installer sets up two **user-level** systemd units:

| Unit | Purpose |
|------|---------|
| `ln2t-watchdog.timer` | Fires every night at 02:00 (with up to 15 min jitter). Persistent — catches up after reboot. |
| `ln2t-watchdog.service` | Runs `ln2t-watchdog run` once per timer trigger. |

Useful commands:

```bash
# Check timer status
systemctl --user status ln2t-watchdog.timer

# View service logs
journalctl --user -u ln2t-watchdog.service

# Manually trigger the service
systemctl --user start ln2t-watchdog.service

# Temporarily disable nightly runs
systemctl --user stop ln2t-watchdog.timer

# Re-enable
systemctl --user start ln2t-watchdog.timer
```

---

## Duplicate prevention

**Automatic duplicate prevention** is enabled by default when running `ln2t-watchdog run`. 

### How it works

When the watchdog is triggered (either manually or by the nightly systemd timer), it:

1. Scans for any jobs already running (same tool, same dataset)
2. **Skips** launching duplicates — only launches tools that aren't currently running
3. Logs which jobs were skipped due to being already running
4. Returns a summary of launched vs. skipped jobs

This prevents the common scenario where:
- A tool started running at 02:00 night before 
- Not yet finished when the next nightly trigger fires at 02:00
- Without prevention: two instances of the same tool would compete for resources

### Override with --force

If you need to launch jobs even if duplicates exist, use the `--force` flag:

```bash
ln2t-watchdog run --force
```

This bypasses duplicate prevention and launches all configured jobs. Useful when manually testing or if you explicitly want multiple instances.

---

## Logs

Each tool invocation writes two files in
`~/code/<dataset>-code/ln2t_watchdog/logs/`:

| File | Content |
|------|---------|
| `<tool>_<YYYYmmdd_HHMMSS>_stdout.log` | Standard output |
| `<tool>_<YYYYmmdd_HHMMSS>_stderr.log` | Standard error |

A global run history is kept in `~/.local/state/ln2t_watchdog/run_history.log`.

---


