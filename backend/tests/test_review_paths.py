"""Tests for persisted review path configuration endpoints."""

from pathlib import Path

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


def test_get_review_paths_returns_persisted_values(tmp_path: Path) -> None:
    """The listing endpoint should return known paths from config.yaml."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    known_path = tmp_path / "known"
    known_path.mkdir(parents=True)
    (state_directory / "config.yaml").write_text(
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
        "hiddenPickerPaths": [str(hidden_path)],
    }
