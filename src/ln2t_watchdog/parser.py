"""Parse ln2t_watchdog YAML configuration files into command descriptors."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """Parsed specification for a single tool invocation."""

    tool_name: str
    dataset_name: str
    version: Optional[str] = None
    tool_args: Optional[str] = None
    participant_labels: List[str] = field(default_factory=list)

    # Back-reference to originating config file (useful for logging)
    config_file: Optional[Path] = None

    def build_command(self) -> List[str]:
        """Build the ``ln2t_tools`` command as a list of arguments."""
        cmd: List[str] = ["ln2t_tools", self.tool_name, "--dataset", self.dataset_name]

        if self.version:
            cmd.extend(["--version", self.version])

        if self.tool_args:
            cmd.extend(["--tool-args", self.tool_args])

        if self.participant_labels:
            cmd.append("--participant-label")
            cmd.extend(self.participant_labels)

        return cmd

    def build_command_string(self) -> str:
        """Return a shell-friendly string representation of the command."""
        parts: List[str] = ["ln2t_tools", self.tool_name, "--dataset", self.dataset_name]

        if self.version:
            parts.extend(["--version", self.version])

        if self.tool_args:
            # Wrap tool_args in quotes so it stays a single argument
            parts.extend(["--tool-args", f'"{self.tool_args}"'])

        if self.participant_labels:
            parts.append("--participant-label")
            parts.extend(self.participant_labels)

        return " ".join(parts)


def parse_config_file(config_path: Path, dataset_name: str) -> List[ToolSpec]:
    """Parse a single YAML configuration file and return tool specifications.

    Expected YAML structure::

        ln2t_tools:
          freesurfer:
            version: "7.2.0"
            tool_args: "--recon-all all"
            participant-label:
              - "001"
              - "042"
          fmriprep:
            version: "21.1.4"
            tool_args: "--fs-noreconall"
            participant-label:
              - "001"
    """
    try:
        data = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as exc:
        logger.error("Failed to parse %s: %s", config_path, exc)
        return []
    except OSError as exc:
        logger.error("Failed to read %s: %s", config_path, exc)
        return []

    if not isinstance(data, dict):
        logger.warning("Unexpected top-level type in %s (expected mapping)", config_path)
        return []

    tools_section = data.get("ln2t_tools")
    if tools_section is None:
        logger.warning("No 'ln2t_tools' key found in %s", config_path)
        return []

    return _parse_tools_section(tools_section, dataset_name, config_path)


def _parse_tools_section(
    tools_section: object,
    dataset_name: str,
    config_path: Path,
) -> List[ToolSpec]:
    """Handle both mapping and list forms of the tool section."""
    specs: List[ToolSpec] = []

    if isinstance(tools_section, dict):
        items = tools_section.items()
    elif isinstance(tools_section, list):
        # Support list-of-dicts: [{"freesurfer": {...}}, {"fmriprep": {...}}]
        items = []
        for entry in tools_section:
            if isinstance(entry, dict):
                items.extend(entry.items())
            else:
                logger.warning("Skipping non-dict list entry in %s: %r", config_path, entry)
    else:
        logger.warning(
            "Unexpected type for 'ln2t_tools' in %s: %s",
            config_path,
            type(tools_section).__name__,
        )
        return []

    for tool_name, options in items:
        if options is None:
            options = {}
        if not isinstance(options, dict):
            logger.warning(
                "Options for tool '%s' in %s should be a mapping, got %s",
                tool_name,
                config_path,
                type(options).__name__,
            )
            continue

        version = options.get("version")
        tool_args = options.get("tool_args") or options.get("tool-args")
        participant_labels_raw = options.get("participant-label") or options.get("participant_label")

        participant_labels: List[str] = []
        if isinstance(participant_labels_raw, list):
            participant_labels = [str(p) for p in participant_labels_raw]
        elif participant_labels_raw is not None:
            participant_labels = [str(participant_labels_raw)]

        specs.append(
            ToolSpec(
                tool_name=str(tool_name),
                dataset_name=dataset_name,
                version=str(version) if version is not None else None,
                tool_args=str(tool_args) if tool_args is not None else None,
                participant_labels=participant_labels,
                config_file=config_path,
            )
        )

    return specs
