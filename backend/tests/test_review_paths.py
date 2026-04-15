"""Tests for persisted review path configuration endpoints."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def test_add_review_path_persists_config(tmp_path: Path) -> None:
    """Posting a review path should persist it to config.yaml."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.post(
        "/api/review-paths",
        json={"path": str(review_directory)},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload == {
        "addedPath": str(review_directory.resolve()),
        "knownPaths": [str(review_directory.resolve())],
    }
    config_content = (state_directory / "config.yaml").read_text(encoding="utf-8")
    assert "known_paths:" in config_content
    assert str(review_directory.resolve()) in config_content
    assert "server:" in config_content
    assert "backend_port: 5000" in config_content
    assert "trusted_hosts: []" in config_content


def test_add_review_path_preserves_existing_server_config(tmp_path: Path) -> None:
    """Adding a path should not remove existing server listen/port settings."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    (state_directory / "config.yaml").write_text(
        "known_paths: []\n"
        "server:\n"
        "  backend_host: 0.0.0.0\n"
        "  backend_port: 5050\n"
        "  frontend_host: 0.0.0.0\n"
        "  frontend_port: 4173\n",
        encoding="utf-8",
    )

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.post("/api/review-paths", json={"path": str(review_directory.resolve())})

    assert response.status_code == 201
    config_content = (state_directory / "config.yaml").read_text(encoding="utf-8")
    assert "backend_host: 0.0.0.0" in config_content
    assert "backend_port: 5050" in config_content
    assert "frontend_port: 4173" in config_content


def test_add_review_path_preserves_existing_trusted_hosts(tmp_path: Path) -> None:
    """Adding a path should not remove YAML trusted host configuration."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    (state_directory / "config.yaml").write_text(
        "known_paths: []\n"
        "server:\n"
        "  backend_host: 127.0.0.1\n"
        "  backend_port: 5200\n"
        "  frontend_host: 0.0.0.0\n"
        "  frontend_port: 6913\n"
        "  trusted_hosts:\n"
        "    - somehost\n",
        encoding="utf-8",
    )

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.post("/api/review-paths", json={"path": str(review_directory.resolve())})

    assert response.status_code == 201
    config_content = (state_directory / "config.yaml").read_text(encoding="utf-8")
    assert "trusted_hosts:" in config_content
    assert "- somehost" in config_content


def test_get_review_paths_returns_persisted_values(tmp_path: Path) -> None:
    """The listing endpoint should return known paths from config.yaml."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    known_path = tmp_path / "known"
    known_path.mkdir(parents=True)
    available_path = tmp_path / "available"
    available_path.mkdir(parents=True)
    (state_directory / "config.yaml").write_text(
        "available_paths:\n  - " + str(available_path.resolve()) + "\n"
        "known_paths:\n  - " + str(known_path.resolve()) + "\n",
        encoding="utf-8",
    )
    hidden_path = tmp_path / "hidden"

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(hidden_path,),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.get("/api/review-paths")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "knownPaths": [str(known_path.resolve())],
        "availablePaths": [str(available_path.resolve())],
        "hiddenPickerPaths": [str(hidden_path)],
    }


def test_remove_review_path_removes_entry(tmp_path: Path) -> None:
    """DELETE /api/review-paths should remove the path and return the updated list."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    path_a = tmp_path / "path_a"
    path_b = tmp_path / "path_b"
    path_a.mkdir()
    path_b.mkdir()
    (state_directory / "config.yaml").write_text(
        "known_paths:\n  - " + str(path_a.resolve()) + "\n  - " + str(path_b.resolve()) + "\n",
        encoding="utf-8",
    )

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.delete("/api/review-paths", json={"path": str(path_a.resolve())})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "removedPath": str(path_a.resolve()),
        "knownPaths": [str(path_b.resolve())],
    }
    config_content = (state_directory / "config.yaml").read_text(encoding="utf-8")
    assert str(path_a.resolve()) not in config_content
    assert str(path_b.resolve()) in config_content


def test_remove_review_path_returns_404_for_unknown_path(tmp_path: Path) -> None:
    """DELETE /api/review-paths should return 404 when the path is not configured."""

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
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.delete("/api/review-paths", json={"path": str(tmp_path / "nonexistent")})

    assert response.status_code == 404
    payload = response.get_json()
    assert "error" in payload


def test_add_review_path_starts_thumbnail_warm_thread(tmp_path: Path) -> None:
    """Adding a path with auto_thumbnail_on_add=True must start the warm thread."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
        auto_thumbnail_on_add=True,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    mock_thread = MagicMock()
    with patch("mediareviewer_api.api.threading.Thread", return_value=mock_thread) as mock_cls:
        response = client.post(
            "/api/review-paths",
            json={"path": str(review_directory)},
        )

    assert response.status_code == 201
    mock_cls.assert_called_once()
    call_kwargs = mock_cls.call_args
    assert call_kwargs.kwargs.get("daemon") is True
    assert "thumb-warm" in (call_kwargs.kwargs.get("name") or "")
    mock_thread.start.assert_called_once()


def test_add_review_path_skips_warm_thread_when_disabled(tmp_path: Path) -> None:
    """Adding a path with auto_thumbnail_on_add=False must not start the warm thread."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
        auto_thumbnail_on_add=False,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    with patch("mediareviewer_api.api.threading.Thread") as mock_cls:
        response = client.post(
            "/api/review-paths",
            json={"path": str(review_directory)},
        )

    assert response.status_code == 201
    # The scan-stream endpoint also uses threading.Thread; here we only POSTed
    # a path, so the Thread constructor must not have been called at all.
    mock_cls.assert_not_called()
