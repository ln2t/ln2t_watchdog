"""Discover dataset directories and their ln2t_watchdog configuration files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# Pattern: YYYY-Adjective_Animal-randomString-code
DATASET_DIR_RE = re.compile(
    r"^(\d{4}-.+)-code$"
)


@dataclass
class DatasetConfig:
    """A discovered dataset together with its configuration file paths."""

    dataset_dir: Path
    dataset_name: str
    config_files: List[Path] = field(default_factory=list)


def derive_dataset_name(folder_name: str) -> str | None:
    """Extract the dataset name from a code-directory name.

    ``2024-Happy_Dog-abc123-code`` → ``2024-Happy_Dog-abc123``

    Returns *None* when the folder name does not match the expected pattern.
    """
    match = DATASET_DIR_RE.match(folder_name)
    if match:
        return match.group(1)
    return None


def scan_code_directory(code_dir: Path | None = None) -> List[DatasetConfig]:
    """Scan *code_dir* (default ``~/code``) for dataset configuration files.

    Returns a list of :class:`DatasetConfig` objects, one per dataset that
    contains at least one ``ln2t_watchdog/*.yaml`` file.
    """
    if code_dir is None:
        code_dir = Path.home() / "code"

    if not code_dir.is_dir():
        return []

    results: List[DatasetConfig] = []

    for entry in sorted(code_dir.iterdir()):
        if not entry.is_dir():
            continue

        dataset_name = derive_dataset_name(entry.name)
        if dataset_name is None:
            continue

        watchdog_dir = entry / "ln2t_watchdog"
        if not watchdog_dir.is_dir():
            continue

        yaml_files = sorted(
            p for p in watchdog_dir.iterdir()
            if p.is_file() and p.suffix in (".yaml", ".yml")
        )

        if yaml_files:
            results.append(
                DatasetConfig(
                    dataset_dir=entry,
                    dataset_name=dataset_name,
                    config_files=yaml_files,
                )
            )

    return results
