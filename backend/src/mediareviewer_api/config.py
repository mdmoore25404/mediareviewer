"""Typed application configuration for the Media Reviewer API."""

import os
from dataclasses import dataclass, field
from pathlib import Path

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

    @classmethod
    def from_env(cls) -> "AppSettings":
        """Load settings from environment variables using conservative defaults."""

        state_directory = Path(
            os.getenv("MEDIAREVIEWER_STATE_DIR", str(Path.home() / ".mediareviewer")),
        ).expanduser()
        return cls(
            host=os.getenv("MEDIAREVIEWER_HOST", "127.0.0.1"),
            port=int(os.getenv("MEDIAREVIEWER_PORT", "5000")),
            state_directory=state_directory,
            hidden_picker_paths=_parse_hidden_paths(os.getenv("MEDIAREVIEWER_HIDDEN_PATHS")),
            deletion_workers=int(os.getenv("MEDIAREVIEWER_DELETION_WORKERS", "2")),
        )
