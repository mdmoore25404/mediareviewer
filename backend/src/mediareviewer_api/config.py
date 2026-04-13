"""Typed application configuration for the Media Reviewer API."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_HIDDEN_PICKER_PATHS: tuple[Path, ...] = (
    Path("/dev"),
    Path("/proc"),
    Path("/run"),
    Path("/snap"),
    Path("/sys"),
    Path.home() / ".ssh",
)


def _parse_hidden_paths(raw_value: str | None) -> tuple[Path, ...]:
    """Parse a colon-delimited environment variable into absolute paths."""

    if not raw_value:
        return DEFAULT_HIDDEN_PICKER_PATHS

    parsed_paths = [Path(item).expanduser().resolve() for item in raw_value.split(":") if item]
    return tuple(parsed_paths)


def _load_server_settings_from_yaml(
    state_directory: Path,
    config_file_name: str,
) -> tuple[str, int]:
    """Load backend listen host and port from ~/.mediareviewer/config.yaml."""

    config_file_path = state_directory / config_file_name
    if not config_file_path.exists():
        return ("127.0.0.1", 5000)

    raw_data = yaml.safe_load(config_file_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        return ("127.0.0.1", 5000)

    raw_server = raw_data.get("server", {})
    if not isinstance(raw_server, dict):
        return ("127.0.0.1", 5000)

    host = str(raw_server.get("backend_host", "127.0.0.1"))
    port = int(raw_server.get("backend_port", 5000))
    return (host, port)


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Configuration values used to bootstrap the API and review services."""

    host: str = "127.0.0.1"
    port: int = 5000
    state_directory: Path = field(default_factory=lambda: Path.home() / ".mediareviewer")
    hidden_picker_paths: tuple[Path, ...] = field(
        default_factory=lambda: DEFAULT_HIDDEN_PICKER_PATHS,
    )
    deletion_workers: int = 2
    config_file_name: str = "config.yaml"

    @property
    def config_file_path(self) -> Path:
        """Return the path to the persistent user configuration file."""

        return self.state_directory / self.config_file_name

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Load settings from environment variables using conservative defaults."""

        state_directory = Path(
            os.getenv("MEDIAREVIEWER_STATE_DIR", str(Path.home() / ".mediareviewer")),
        ).expanduser()
        yaml_host, yaml_port = _load_server_settings_from_yaml(state_directory, "config.yaml")
        return cls(
            host=os.getenv("MEDIAREVIEWER_HOST", yaml_host),
            port=int(os.getenv("MEDIAREVIEWER_PORT", str(yaml_port))),
            state_directory=state_directory,
            hidden_picker_paths=_parse_hidden_paths(os.getenv("MEDIAREVIEWER_HIDDEN_PATHS")),
            deletion_workers=int(os.getenv("MEDIAREVIEWER_DELETION_WORKERS", "2")),
        )
