"""Tests for the POST /api/media-items/batch endpoint."""

from pathlib import Path

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def _make_app(tmp_path: Path, review_directory: Path) -> FlaskClient:
    """Create a test app with one known review path and return a test client."""
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


def test_batch_seen_marks_multiple_items(tmp_path: Path) -> None:
    """POST /api/media-items/batch with action=seen should mark all paths as seen."""

    review_dir = tmp_path / "media"
    review_dir.mkdir(parents=True)
    file_a = review_dir / "a.jpg"
    file_b = review_dir / "b.jpg"
    file_a.write_bytes(b"img")
    file_b.write_bytes(b"img")

    client = _make_app(tmp_path, review_dir)

    resp = client.post(
        "/api/media-items/batch",
        json={"paths": [str(file_a), str(file_b)], "action": "seen"},
    )

    assert resp.status_code == 207
    payload = resp.get_json()
    assert "results" in payload
    assert len(payload["results"]) == 2
    for result in payload["results"]:
        assert result["error"] is None
        assert result["status"]["seen"] is True


def test_batch_locked_item_returns_error_entry(tmp_path: Path) -> None:
    """Batch trash on a locked item should produce an error entry, not 409."""

    review_dir = tmp_path / "media"
    review_dir.mkdir(parents=True)
    locked_file = review_dir / "clip.mp4"
    safe_file = review_dir / "safe.mp4"
    locked_file.write_bytes(b"video")
    safe_file.write_bytes(b"video")

    client = _make_app(tmp_path, review_dir)

    # Lock the first file
    lock_resp = client.post(
        "/api/media-actions",
        json={"path": str(locked_file), "action": "lock"},
    )
    assert lock_resp.status_code == 200

    # Batch trash both — locked one should error, safe one should succeed
    resp = client.post(
        "/api/media-items/batch",
        json={"paths": [str(locked_file), str(safe_file)], "action": "trash"},
    )

    assert resp.status_code == 207
    payload = resp.get_json()
    results = {r["path"]: r for r in payload["results"]}

    locked_result = results[str(locked_file)]
    assert locked_result["error"] is not None
    assert "lock" in locked_result["error"].lower()

    safe_result = results[str(safe_file)]
    assert safe_result["error"] is None
    assert safe_result["status"]["trashed"] is True
    assert safe_result["newPath"] is not None


def test_batch_returns_400_for_empty_paths(tmp_path: Path) -> None:
    """Empty paths array should be rejected with 400."""

    review_dir = tmp_path / "media"
    review_dir.mkdir(parents=True)
    client = _make_app(tmp_path, review_dir)

    resp = client.post(
        "/api/media-items/batch",
        json={"paths": [], "action": "seen"},
    )

    assert resp.status_code == 400
    assert "paths" in resp.get_json()["error"].lower()


def test_batch_returns_400_for_invalid_action(tmp_path: Path) -> None:
    """Unknown action value should be rejected with 400."""

    review_dir = tmp_path / "media"
    review_dir.mkdir(parents=True)
    media_file = review_dir / "img.jpg"
    media_file.write_bytes(b"img")
    client = _make_app(tmp_path, review_dir)

    resp = client.post(
        "/api/media-items/batch",
        json={"paths": [str(media_file)], "action": "teleport"},
    )

    assert resp.status_code == 400
    assert "action" in resp.get_json()["error"].lower()


def test_batch_returns_error_entry_for_missing_file(tmp_path: Path) -> None:
    """A path that does not exist should produce an error entry with no abort."""

    review_dir = tmp_path / "media"
    review_dir.mkdir(parents=True)
    real_file = review_dir / "real.jpg"
    real_file.write_bytes(b"img")
    ghost_path = str(review_dir / "ghost.jpg")

    client = _make_app(tmp_path, review_dir)

    resp = client.post(
        "/api/media-items/batch",
        json={"paths": [ghost_path, str(real_file)], "action": "seen"},
    )

    assert resp.status_code == 207
    payload = resp.get_json()
    results = {r["path"]: r for r in payload["results"]}

    assert results[ghost_path]["error"] is not None
    assert results[str(real_file)]["error"] is None
    assert results[str(real_file)]["status"]["seen"] is True


def test_batch_returns_400_for_too_many_paths(tmp_path: Path) -> None:
    """More than 500 paths should be rejected with 400."""

    review_dir = tmp_path / "media"
    review_dir.mkdir(parents=True)
    client = _make_app(tmp_path, review_dir)

    fake_paths = [str(review_dir / f"f{i}.jpg") for i in range(501)]

    resp = client.post(
        "/api/media-items/batch",
        json={"paths": fake_paths, "action": "seen"},
    )

    assert resp.status_code == 400
    assert "500" in resp.get_json()["error"]
