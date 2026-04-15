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
    """Files inside a .trash/ sibling directory should be permanently deleted."""

    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    keep_file = review_directory / "keep.jpg"
    keep_file.write_bytes(b"img")

    trash_dir = review_directory / ".trash"
    trash_dir.mkdir()
    trash_file = trash_dir / "delete_me.jpg"
    trash_file.write_bytes(b"img")

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


def test_empty_trash_cleans_up_empty_trash_dir(tmp_path: Path) -> None:
    """The .trash/ directory should be removed once all its files are deleted."""

    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    trash_dir = review_directory / ".trash"
    trash_dir.mkdir()
    (trash_dir / "frame001.jpg").write_bytes(b"img")

    client: FlaskClient = _make_client(tmp_path, review_directory)
    response = client.post(
        "/api/empty-trash",
        json={"path": str(review_directory.resolve())},
    )

    assert response.status_code == 200
    events = _parse_ndjson(response)
    done = next(e for e in events if e["type"] == "done")

    assert done["deleted"] == 1
    assert not trash_dir.exists()


def test_empty_trash_handles_nested_trash_dirs(tmp_path: Path) -> None:
    """Files in .trash/ directories at multiple nesting levels are all deleted."""

    review_directory = tmp_path / "review"
    sub_dir = review_directory / "DCIM" / "100MEDIA"
    sub_dir.mkdir(parents=True)

    # .trash/ at top level
    top_trash = review_directory / ".trash"
    top_trash.mkdir()
    top_file = top_trash / "top.jpg"
    top_file.write_bytes(b"img")

    # .trash/ inside a subdirectory
    sub_trash = sub_dir / ".trash"
    sub_trash.mkdir()
    sub_file = sub_trash / "sub.jpg"
    sub_file.write_bytes(b"img")

    client: FlaskClient = _make_client(tmp_path, review_directory)
    response = client.post(
        "/api/empty-trash",
        json={"path": str(review_directory.resolve())},
    )

    assert response.status_code == 200
    events = _parse_ndjson(response)
    done = next(e for e in events if e["type"] == "done")

    assert done["deleted"] == 2
    assert done["errors"] == 0
    assert not top_file.exists()
    assert not sub_file.exists()


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
