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
    assert media_file.with_suffix(".mp4.seen").exists()
    assert not media_file.with_suffix(".mp4.trash").exists()

    trash_response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "trash"},
    )

    assert trash_response.status_code == 200
    payload = trash_response.get_json()
    assert payload["status"] == {"locked": False, "trashed": True, "seen": True}
    assert not media_file.with_suffix(".mp4.lock").exists()
    assert media_file.with_suffix(".mp4.trash").exists()
    assert media_file.with_suffix(".mp4.seen").exists()


def test_trash_implies_seen(tmp_path: Path) -> None:
    """Trash action should also mark the item as seen."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    media_file = review_directory / "clip002.mp4"
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

    response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "trash"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"]["trashed"] is True
    assert payload["status"]["seen"] is True


def test_untrash_action(tmp_path: Path) -> None:
    """Untrash action should remove the .trash companion file."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    media_file = review_directory / "clip003.mp4"
    media_file.write_bytes(b"video")
    media_file.with_suffix(".mp4.trash").write_text("", encoding="utf-8")

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

    response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "untrash"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"]["trashed"] is False
    assert not media_file.with_suffix(".mp4.trash").exists()


def test_unlock_action(tmp_path: Path) -> None:
    """Unlock action should remove the .lock companion file."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    media_file = review_directory / "clip004.mp4"
    media_file.write_bytes(b"video")
    media_file.with_suffix(".mp4.lock").write_text("", encoding="utf-8")

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

    response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "unlock"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"]["locked"] is False
    assert not media_file.with_suffix(".mp4.lock").exists()


def test_lock_implies_seen(tmp_path: Path) -> None:
    """Lock action should also mark the item as seen."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    media_file = review_directory / "clip005.mp4"
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

    response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "lock"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"]["locked"] is True
    assert payload["status"]["seen"] is True
    assert media_file.with_suffix(".mp4.seen").exists()
