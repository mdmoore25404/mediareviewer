"""Tests for the initial Media Reviewer API scaffold."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask.testing import FlaskClient

from mediareviewer_api.app import _configure_logging, create_app
from mediareviewer_api.config import AppSettings


def test_health_endpoint_returns_configured_status(tmp_path: Path) -> None:
    """The health route should expose the scaffold status payload."""

    settings = AppSettings(
        state_directory=tmp_path,
        hidden_picker_paths=(tmp_path / "hidden",),
        deletion_workers=3,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "status": "ok",
        "service": "mediareviewer-api",
        "settings": {
            "stateDirectory": str(tmp_path),
            "hiddenPickerPaths": [str(tmp_path / "hidden")],
            "deletionWorkers": 3,
            "videoPreloadMb": 50,
        },
        "deletionQueue": {
            "max_workers": 3,
            "active_jobs": 0,
            "submitted_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
        },
    }


def test_settings_load_host_port_from_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """App settings should honor YAML server defaults when env vars are unset."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    config_path = state_directory / "config.yaml"
    config_path.write_text(
        "known_paths: []\nserver:\n  backend_host: 0.0.0.0\n  backend_port: 5050\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("MEDIAREVIEWER_STATE_DIR", str(state_directory))
    monkeypatch.delenv("MEDIAREVIEWER_HOST", raising=False)
    monkeypatch.delenv("MEDIAREVIEWER_PORT", raising=False)

    settings = AppSettings.from_env()

    assert settings.host == "0.0.0.0"
    assert settings.port == 5050


def test_settings_load_trusted_hosts_from_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """App settings should load additional trusted hosts from YAML config."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    config_path = state_directory / "config.yaml"
    config_path.write_text(
        "known_paths: []\n"
        "server:\n"
        "  backend_host: 127.0.0.1\n"
        "  backend_port: 5200\n"
        "  trusted_hosts:\n"
        "    - somehost\n"
        "    - mediareviewer.local\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("MEDIAREVIEWER_STATE_DIR", str(state_directory))
    settings = AppSettings.from_env()

    assert settings.trusted_hosts == ("somehost", "mediareviewer.local")


def test_startup_warmup_spawns_thread_per_known_path(tmp_path: Path) -> None:
    """create_app should start one warm thread per known path when auto_thumbnail_on_add=True."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    path_a = tmp_path / "path_a"
    path_b = tmp_path / "path_b"
    path_a.mkdir()
    path_b.mkdir()
    (state_directory / "config.yaml").write_text(
        "known_paths:\n"
        f"  - {path_a.resolve()}\n"
        f"  - {path_b.resolve()}\n",
        encoding="utf-8",
    )

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
        auto_thumbnail_on_add=True,
    )

    mock_thread = MagicMock()
    with patch("mediareviewer_api.app.threading.Thread", return_value=mock_thread) as mock_cls:
        create_app(settings)

    assert mock_cls.call_count == 2
    started_names = [c.kwargs.get("name", "") for c in mock_cls.call_args_list]
    assert any("path_a" in n for n in started_names)
    assert any("path_b" in n for n in started_names)
    assert mock_thread.start.call_count == 2


def test_startup_warmup_skipped_when_disabled(tmp_path: Path) -> None:
    """create_app must not start warm threads when auto_thumbnail_on_add=False."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    known = tmp_path / "media"
    known.mkdir()
    (state_directory / "config.yaml").write_text(
        f"known_paths:\n  - {known.resolve()}\n",
        encoding="utf-8",
    )

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
        auto_thumbnail_on_add=False,
    )

    with patch("mediareviewer_api.app.threading.Thread") as mock_cls:
        create_app(settings)

    mock_cls.assert_not_called()


def test_startup_warmup_skipped_when_no_known_paths(tmp_path: Path) -> None:
    """create_app must not start any threads when no known paths are configured."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    (state_directory / "config.yaml").write_text(
        "known_paths: []\n",
        encoding="utf-8",
    )

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
        auto_thumbnail_on_add=True,
    )

    with patch("mediareviewer_api.app.threading.Thread") as mock_cls:
        create_app(settings)

    mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# log_level configuration tests
# ---------------------------------------------------------------------------


def test_app_settings_default_log_level_is_info() -> None:
    """AppSettings default log_level must be INFO (debug output off by default)."""

    settings = AppSettings()
    assert settings.log_level == "INFO"


def test_app_settings_log_level_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MEDIAREVIEWER_LOG_LEVEL env var must override the default log level."""

    monkeypatch.setenv("MEDIAREVIEWER_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEDIAREVIEWER_LOG_LEVEL", "debug")
    settings = AppSettings.from_env()
    assert settings.log_level == "DEBUG"


def test_app_settings_log_level_from_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """server.log_level in config.yaml must be read into AppSettings.log_level."""

    (tmp_path / "config.yaml").write_text(
        "server:\n  log_level: WARNING\n", encoding="utf-8"
    )
    monkeypatch.setenv("MEDIAREVIEWER_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("MEDIAREVIEWER_LOG_LEVEL", raising=False)
    settings = AppSettings.from_env()
    assert settings.log_level == "WARNING"


def test_configure_logging_creates_log_file(tmp_path: Path) -> None:
    """_configure_logging must create the log file and set the requested level."""

    log_file = tmp_path / "app.log"
    pkg_logger = logging.getLogger("mediareviewer_api")
    saved_handlers = pkg_logger.handlers[:]
    saved_level = pkg_logger.level
    saved_propagate = pkg_logger.propagate
    pkg_logger.handlers.clear()
    try:
        _configure_logging("DEBUG", log_file)
        assert log_file.exists()
        assert pkg_logger.level == logging.DEBUG
        handler_types = {type(h).__name__ for h in pkg_logger.handlers}
        assert "StreamHandler" in handler_types
        assert "RotatingFileHandler" in handler_types
    finally:
        for h in list(pkg_logger.handlers):
            h.close()
            pkg_logger.removeHandler(h)
        pkg_logger.handlers.extend(saved_handlers)
        pkg_logger.setLevel(saved_level)
        pkg_logger.propagate = saved_propagate