"""Persistent YAML-backed configuration for review folder paths."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class DevServerSettings:
    """Development listen and port settings persisted in config.yaml."""

    backend_host: str = "127.0.0.1"
    backend_port: int = 5000
    frontend_host: str = "0.0.0.0"
    frontend_port: int = 5173
    trusted_hosts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewConfig:
    """Configuration persisted to ~/.mediareviewer/config.yaml."""

    known_paths: tuple[Path, ...]
    server: DevServerSettings


class ReviewConfigStore:
    """Load and update known review paths in a small YAML file."""

    def __init__(self, config_file_path: Path) -> None:
        self._config_file_path = config_file_path

    def load(self) -> ReviewConfig:
        """Load known paths from disk, returning defaults when no file exists."""

        default_server = DevServerSettings()
        if not self._config_file_path.exists():
            return ReviewConfig(known_paths=(), server=default_server)

        raw_data = yaml.safe_load(self._config_file_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            return ReviewConfig(known_paths=(), server=default_server)

        raw_paths = raw_data.get("known_paths", [])
        if not isinstance(raw_paths, list):
            raw_paths = []

        raw_server = raw_data.get("server", {})
        if not isinstance(raw_server, dict):
            raw_server = {}
        server = DevServerSettings(
            backend_host=str(raw_server.get("backend_host", default_server.backend_host)),
            backend_port=int(raw_server.get("backend_port", default_server.backend_port)),
            frontend_host=str(raw_server.get("frontend_host", default_server.frontend_host)),
            frontend_port=int(raw_server.get("frontend_port", default_server.frontend_port)),
            trusted_hosts=tuple(
                str(item)
                for item in raw_server.get("trusted_hosts", default_server.trusted_hosts)
                if isinstance(item, str) and item
            ),
        )

        resolved_paths: list[Path] = []
        for item in raw_paths:
            if isinstance(item, str) and item:
                resolved_paths.append(Path(item).expanduser().resolve())
        return ReviewConfig(known_paths=tuple(resolved_paths), server=server)

    def add_known_path(self, review_path: Path) -> ReviewConfig:
        """Add a known review path and persist the updated configuration."""

        current = self.load()
        normalized = review_path.expanduser().resolve()
        combined = set(current.known_paths)
        combined.add(normalized)
        ordered_paths = tuple(sorted(combined, key=lambda value: str(value)))
        updated = ReviewConfig(known_paths=ordered_paths, server=current.server)
        self._write(updated)
        return updated

    def remove_known_path(self, review_path: Path) -> ReviewConfig:
        """Remove a known review path and persist the updated configuration."""

        current = self.load()
        normalized = review_path.expanduser().resolve()
        remaining = tuple(p for p in current.known_paths if p != normalized)
        updated = ReviewConfig(known_paths=remaining, server=current.server)
        self._write(updated)
        return updated

    def _write(self, config: ReviewConfig) -> None:
        """Write the YAML configuration file, creating the parent directory if needed."""

        self._config_file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "known_paths": [str(path) for path in config.known_paths],
            "server": {
                "backend_host": config.server.backend_host,
                "backend_port": config.server.backend_port,
                "frontend_host": config.server.frontend_host,
                "frontend_port": config.server.frontend_port,
                "trusted_hosts": list(config.server.trusted_hosts),
            },
        }
        self._config_file_path.write_text(
            yaml.safe_dump(payload, sort_keys=True),
            encoding="utf-8",
        )
