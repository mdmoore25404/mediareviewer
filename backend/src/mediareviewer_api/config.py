"""Typed application configuration for the Media Reviewer API."""

import os
import platform
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


def _default_thumbnail_cache_directory(state_directory: Path) -> Path:
    """Return the default on-disk thumbnail cache root for this platform."""

    system_name = platform.system()
    if system_name == "Linux":
        xdg_cache_home = Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))).expanduser()
        return xdg_cache_home / "thumbnails"
    return state_directory / "thumbnails"


def _load_server_settings_from_yaml(
    state_directory: Path,
    config_file_name: str,
) -> tuple[str, int, tuple[str, ...]]:
    """Load backend listen host and port from ~/.mediareviewer/config.yaml."""

    config_file_path = state_directory / config_file_name
    if not config_file_path.exists():
        return ("127.0.0.1", 5000, ())

    raw_data = yaml.safe_load(config_file_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        return ("127.0.0.1", 5000, ())

    raw_server = raw_data.get("server", {})
    if not isinstance(raw_server, dict):
        return ("127.0.0.1", 5000, ())

    host = str(raw_server.get("backend_host", "127.0.0.1"))
    port = int(raw_server.get("backend_port", 5000))
    trusted_hosts = tuple(
        str(item)
        for item in raw_server.get("trusted_hosts", [])
        if isinstance(item, str) and item
    )
    return (host, port, trusted_hosts)


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Configuration values used to bootstrap the API and review services."""

    host: str = "127.0.0.1"
    port: int = 5000
    state_directory: Path = field(default_factory=lambda: Path.home() / ".mediareviewer")
    hidden_picker_paths: tuple[Path, ...] = field(
        default_factory=lambda: DEFAULT_HIDDEN_PICKER_PATHS,
    )
    trusted_hosts: tuple[str, ...] = ()
    deletion_workers: int = 2
    video_preload_mb: int = 50
    auto_thumbnail_on_add: bool = True
    thumbnail_cache_directory: Path = field(
        default_factory=lambda: _default_thumbnail_cache_directory(Path.home() / ".mediareviewer"),
    )
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
        yaml_host, yaml_port, yaml_trusted_hosts = _load_server_settings_from_yaml(
            state_directory,
            "config.yaml",
        )
        return cls(
            host=os.getenv("MEDIAREVIEWER_HOST", yaml_host),
            port=int(os.getenv("MEDIAREVIEWER_PORT", str(yaml_port))),
            state_directory=state_directory,
            hidden_picker_paths=_parse_hidden_paths(os.getenv("MEDIAREVIEWER_HIDDEN_PATHS")),
            trusted_hosts=yaml_trusted_hosts,
            deletion_workers=int(os.getenv("MEDIAREVIEWER_DELETION_WORKERS", "2")),
            video_preload_mb=int(os.getenv("MEDIAREVIEWER_VIDEO_PRELOAD_MB", "50")),
            auto_thumbnail_on_add=os.getenv(
                "MEDIAREVIEWER_AUTO_THUMBNAIL_ON_ADD", "true"
            ).lower() not in ("false", "0", "no"),
            thumbnail_cache_directory=Path(
                os.getenv(
                    "MEDIAREVIEWER_THUMBNAIL_CACHE_DIR",
                    str(_default_thumbnail_cache_directory(state_directory)),
                ),
            ).expanduser(),
        )
