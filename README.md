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
    └── ln2t_watchdog/
        ├── my_pipelines.yaml           # configuration file(s)
        └── logs/                        # created automatically
            ├── freesurfer_20260225_020012_stdout.log
            ├── freesurfer_20260225_020012_stderr.log
            └── …
```

## Configuration file format

Place one or more `.yaml` files in `~/code/<dataset>-code/ln2t_watchdog/`.

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
| `run`     | Scan all configs and launch commands. Use `--dry-run` / `-n` to preview. |
| `list`    | List discovered datasets and the commands that would be generated. |
| `status`  | Print a status report (last run, systemd timer state, recent logs). |
| `logs`    | Show recent log files, optionally filtered by dataset name. |
| `init`    | Generate a template configuration file. |

### Examples

```bash
# Generate a template config file
ln2t-watchdog init -o my_pipelines.yaml

# Preview what would run
ln2t-watchdog run --dry-run

# Actually launch everything
ln2t-watchdog run

# Show status
ln2t-watchdog status

# List all discovered pipelines
ln2t-watchdog list

# Show logs for a specific dataset
ln2t-watchdog logs 2024-Happy_Dog-abc123
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

## Logs

Each tool invocation writes two files in
`~/code/<dataset>-code/ln2t_watchdog/logs/`:

| File | Content |
|------|---------|
| `<tool>_<YYYYmmdd_HHMMSS>_stdout.log` | Standard output |
| `<tool>_<YYYYmmdd_HHMMSS>_stderr.log` | Standard error |

A global run history is kept in `~/.local/state/ln2t_watchdog/run_history.log`.

---


