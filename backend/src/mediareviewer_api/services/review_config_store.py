"""Persistent YAML-backed configuration for review folder paths."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class ReviewConfig:
    """Configuration persisted to ~/.mediareviewer/config.yaml."""

    known_paths: tuple[Path, ...]


class ReviewConfigStore:
    """Load and update known review paths in a small YAML file."""

    def __init__(self, config_file_path: Path) -> None:
        self._config_file_path = config_file_path

    def load(self) -> ReviewConfig:
        """Load known paths from disk, returning defaults when no file exists."""

        if not self._config_file_path.exists():
            return ReviewConfig(known_paths=())

        raw_data = yaml.safe_load(self._config_file_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            return ReviewConfig(known_paths=())

        raw_paths = raw_data.get("known_paths", [])
        if not isinstance(raw_paths, list):
            return ReviewConfig(known_paths=())

        resolved_paths: list[Path] = []
        for item in raw_paths:
            if isinstance(item, str) and item:
                resolved_paths.append(Path(item).expanduser().resolve())
        return ReviewConfig(known_paths=tuple(resolved_paths))

    def add_known_path(self, review_path: Path) -> ReviewConfig:
        """Add a known review path and persist the updated configuration."""

        current = self.load()
        normalized = review_path.expanduser().resolve()
        combined = set(current.known_paths)
        combined.add(normalized)
        ordered_paths = tuple(sorted(combined, key=lambda value: str(value)))
        updated = ReviewConfig(known_paths=ordered_paths)
        self._write(updated)
        return updated

    def _write(self, config: ReviewConfig) -> None:
        """Write the YAML configuration file, creating the parent directory if needed."""

        self._config_file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "known_paths": [str(path) for path in config.known_paths],
        }
        self._config_file_path.write_text(
            yaml.safe_dump(payload, sort_keys=True),
            encoding="utf-8",
        )
