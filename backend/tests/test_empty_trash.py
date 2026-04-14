"""Tests for the POST /api/empty-trash NDJSON streaming endpoint."""

import json
from pathlib import Path

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def _make_client(tmp_path: Path, review_directory: Path) -> FlaskClient:
    state_directory = tmp_path / "state"
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
    return create_app(settings).test_client()


def _parse_ndjson(response: object) -> list[dict[str, object]]:
    """Parse the NDJSON body of an empty-trash response into a list of events."""
    from flask.testing import FlaskClient  # noqa: F401 — only used via response type

    data = getattr(response, "data", b"")
    return [
        json.loads(line)
        for line in data.decode("utf-8").strip().splitlines()
        if line.strip()
    ]


def test_empty_trash_deletes_trashed_files(tmp_path: Path) -> None:
    """Files with a .trash companion should be permanently deleted."""

    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    keep_file = review_directory / "keep.jpg"
    keep_file.write_bytes(b"img")

    trash_file = review_directory / "delete_me.jpg"
    trash_file.write_bytes(b"img")
    trash_file.with_suffix(".jpg.trash").write_text("", encoding="utf-8")
    trash_file.with_suffix(".jpg.seen").write_text("", encoding="utf-8")

    client: FlaskClient = _make_client(tmp_path, review_directory)
    response = client.post(
        "/api/empty-trash",
        json={"path": str(review_directory.resolve())},
    )

    assert response.status_code == 200
    events = _parse_ndjson(response)
    done = next(e for e in events if e["type"] == "done")
    deleted_events = [e for e in events if e["type"] == "deleted"]

    assert done["deleted"] == 1
    assert done["errors"] == 0
    assert any(e["path"] == str(trash_file.resolve()) for e in deleted_events)

    assert keep_file.exists()
    assert not trash_file.exists()
    assert not trash_file.with_suffix(".jpg.trash").exists()
    assert not trash_file.with_suffix(".jpg.seen").exists()


def test_empty_trash_skips_locked_files(tmp_path: Path) -> None:
    """Files that are both trashed and locked must not be deleted."""

    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    media_file = review_directory / "protected.mp4"
    media_file.write_bytes(b"video")
    media_file.with_suffix(".mp4.trash").write_text("", encoding="utf-8")
    media_file.with_suffix(".mp4.lock").write_text("", encoding="utf-8")

    client: FlaskClient = _make_client(tmp_path, review_directory)
    response = client.post(
        "/api/empty-trash",
        json={"path": str(review_directory.resolve())},
    )

    assert response.status_code == 200
    events = _parse_ndjson(response)
    done = next(e for e in events if e["type"] == "done")
    skipped_events = [e for e in events if e["type"] == "skipped"]

    assert done["deleted"] == 0
    assert any(e["path"] == str(media_file.resolve()) for e in skipped_events)
    assert media_file.exists()
    assert media_file.with_suffix(".mp4.trash").exists()


def test_empty_trash_returns_zero_when_nothing_trashed(tmp_path: Path) -> None:
    """Empty-trash on a clean folder should emit done with deleted=0."""

    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)
    (review_directory / "frame001.jpg").write_bytes(b"img")

    client: FlaskClient = _make_client(tmp_path, review_directory)
    response = client.post(
        "/api/empty-trash",
        json={"path": str(review_directory.resolve())},
    )

    assert response.status_code == 200
    events = _parse_ndjson(response)
    done = next(e for e in events if e["type"] == "done")

    assert done["deleted"] == 0
    assert done["errors"] == 0
