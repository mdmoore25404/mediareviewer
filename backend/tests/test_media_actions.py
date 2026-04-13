"""Tests for lock/trash/seen companion-file action endpoint."""

from pathlib import Path

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def test_media_action_updates_companion_files(tmp_path: Path) -> None:
    """Lock and trash actions should maintain mutual exclusion."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    media_file = review_directory / "clip001.mp4"
    media_file.write_bytes(b"video")

    state_directory.mkdir(parents=True)
    (state_directory / "config.yaml").write_text(
        "known_paths:\n  - " + str(review_directory.resolve()) + "\n",
        encoding="utf-8",
    )

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    lock_response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "lock"},
    )

    assert lock_response.status_code == 200
    assert media_file.with_suffix(".mp4.lock").exists()
    assert not media_file.with_suffix(".mp4.trash").exists()

    trash_response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "trash"},
    )

    assert trash_response.status_code == 200
    payload = trash_response.get_json()
    assert payload["status"] == {"locked": False, "trashed": True, "seen": False}
    assert not media_file.with_suffix(".mp4.lock").exists()
    assert media_file.with_suffix(".mp4.trash").exists()
