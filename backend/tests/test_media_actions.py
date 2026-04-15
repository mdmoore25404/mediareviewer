"""Tests for lock/trash/seen companion-file action endpoint."""

from pathlib import Path

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def test_trash_rejected_when_locked(tmp_path: Path) -> None:
    """Trash action should be rejected with 409 when the item is locked."""

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

    trash_response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "trash"},
    )

    assert trash_response.status_code == 409
    payload = trash_response.get_json()
    assert "locked" in payload["error"].lower()
    # Lock file must still exist — no state mutation on rejection
    assert media_file.with_suffix(".mp4.lock").exists()
    # File must not have been moved to .trash/
    assert media_file.exists()
    assert not (review_directory / ".trash" / "clip001.mp4").exists()


def test_trash_succeeds_after_unlock(tmp_path: Path) -> None:
    """Trash action should succeed once the item has been unlocked."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    media_file = review_directory / "clip001b.mp4"
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

    client.post("/api/media-actions", json={"path": str(media_file.resolve()), "action": "lock"})
    client.post("/api/media-actions", json={"path": str(media_file.resolve()), "action": "unlock"})

    trash_response = client.post(
        "/api/media-actions",
        json={"path": str(media_file.resolve()), "action": "trash"},
    )

    assert trash_response.status_code == 200
    payload = trash_response.get_json()
    assert payload["status"] == {"locked": False, "trashed": True, "seen": True}
    # newPath must point to the .trash/-resident location.
    assert payload["newPath"] == str((review_directory / ".trash" / "clip001b.mp4").resolve())
    # File must be physically moved into the .trash/ sibling directory.
    assert not media_file.exists()
    assert (review_directory / ".trash" / "clip001b.mp4").exists()
    assert not media_file.with_suffix(".mp4.lock").exists()


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
    # newPath must point to the .trash/-resident location.
    assert payload["newPath"] == str((review_directory / ".trash" / "clip002.mp4").resolve())
    # File must be physically moved into the .trash/ sibling directory.
    assert not media_file.exists()
    assert (review_directory / ".trash" / "clip002.mp4").exists()


def test_untrash_action(tmp_path: Path) -> None:
    """Untrash action should move the file back from the .trash/ directory."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    trash_dir = review_directory / ".trash"
    trash_dir.mkdir()
    trash_file = trash_dir / "clip003.mp4"
    trash_file.write_bytes(b"video")

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
        json={"path": str(trash_file.resolve()), "action": "untrash"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"]["trashed"] is False
    # newPath must point to the restored location (parent of .trash/).
    assert payload["newPath"] == str((review_directory / "clip003.mp4").resolve())
    # File must be restored to the parent of .trash/.
    assert not trash_file.exists()
    assert (review_directory / "clip003.mp4").exists()


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
