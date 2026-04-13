"""Tests for the initial Media Reviewer API scaffold."""

from pathlib import Path

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
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
        },
        "deletionQueue": {
            "max_workers": 3,
            "active_jobs": 0,
            "submitted_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
        },
    }
