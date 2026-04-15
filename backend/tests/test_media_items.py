"""Tests for recursive media scanning endpoints."""

from pathlib import Path

from flask.testing import FlaskClient
from PIL import Image

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def test_stream_media_items_returns_supported_files_and_status(tmp_path: Path) -> None:
    """The stream endpoint should yield image/video files with status and metadata fields."""

    import json

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    nested_directory = review_directory / "DCIM" / "100MEDIA"
    nested_directory.mkdir(parents=True)

    image_path = nested_directory / "frame001.jpg"
    Image.new("RGB", (12, 8), color=(64, 32, 16)).save(image_path)
    (nested_directory / "frame001.jpg.seen").write_text("", encoding="utf-8")

    video_path = nested_directory / "clip001.mp4"
    video_path.write_bytes(b"fake-video")
    (nested_directory / "clip001.mp4.lock").write_text("", encoding="utf-8")

    pdf_path = nested_directory / "manual.pdf"
    pdf_path.write_text("ignored", encoding="utf-8")

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

    response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "20"},
    )

    assert response.status_code == 200
    assert response.content_type == "application/x-ndjson"
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    item_lines = lines[:-1]
    done_line = json.loads(lines[-1])

    assert done_line["type"] == "done"
    assert done_line["count"] == 2
    item_names = {json.loads(ln)["name"] for ln in item_lines}
    assert item_names == {"frame001.jpg", "clip001.mp4"}

    items = [json.loads(ln) for ln in item_lines]
    image_item = next(item for item in items if item["name"] == "frame001.jpg")
    assert image_item["mediaType"] == "image"
    assert image_item["status"] == {"locked": False, "trashed": False, "seen": True}
    assert image_item["metadata"] == {"width": 12, "height": 8}
    assert image_item["thumbnailUrl"].startswith("/api/media-thumbnail?")

    video_item = next(item for item in items if item["name"] == "clip001.mp4")
    assert video_item["mediaType"] == "video"
    assert video_item["status"] == {"locked": True, "trashed": False, "seen": False}
    assert video_item["metadata"] == {"width": None, "height": None}
    assert video_item["thumbnailUrl"].startswith("/api/media-thumbnail?")


def test_media_file_serves_known_media_path(tmp_path: Path) -> None:
    """The media file endpoint should stream files under configured review roots."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    review_directory.mkdir(parents=True)
    image_path = review_directory / "frame001.jpg"
    Image.new("RGB", (8, 8), color=(32, 64, 96)).save(image_path)

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

    response = client.get(
        "/api/media-file",
        query_string={"path": str(image_path.resolve())},
    )

    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"
    assert len(response.data) > 0


def test_media_file_rejects_unknown_path(tmp_path: Path) -> None:
    """The media file endpoint should reject files outside configured review roots."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    image_path = tmp_path / "frame001.jpg"
    Image.new("RGB", (8, 8), color=(32, 64, 96)).save(image_path)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.get(
        "/api/media-file",
        query_string={"path": str(image_path.resolve())},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Path is not under a configured review path."}


def test_media_thumbnail_serves_cached_png(tmp_path: Path) -> None:
    """The thumbnail endpoint should generate and serve a cached PNG on disk."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    review_directory.mkdir(parents=True)
    image_path = review_directory / "frame001.jpg"
    Image.new("RGB", (64, 48), color=(32, 64, 96)).save(image_path)

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

    response = client.get(
        "/api/media-thumbnail",
        query_string={"path": str(image_path.resolve()), "size": "256"},
    )

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert len(response.data) > 0
    thumbnail_cache_dir = review_directory / ".thumbnails"
    assert thumbnail_cache_dir.exists()
    assert len(list(thumbnail_cache_dir.glob("**/*.png"))) == 1


def test_stream_media_items_yields_items_progressively(tmp_path: Path) -> None:
    """The stream endpoint must return NDJSON with one item per line and a done sentinel."""

    import json

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    nested_directory = review_directory / "DCIM"
    nested_directory.mkdir(parents=True)

    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(nested_directory / "img_a.jpg")
    Image.new("RGB", (8, 8), color=(4, 5, 6)).save(nested_directory / "img_b.jpg")
    (nested_directory / "notes.txt").write_text("ignored", encoding="utf-8")

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

    response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "10"},
    )

    assert response.status_code == 200
    assert response.content_type == "application/x-ndjson"

    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    assert len(lines) == 3  # two items + done sentinel

    item_lines = lines[:-1]
    done_line = json.loads(lines[-1])

    names = {json.loads(ln)["name"] for ln in item_lines}
    assert names == {"img_a.jpg", "img_b.jpg"}

    for raw in item_lines:
        item = json.loads(raw)
        assert item["mediaType"] == "image"
        assert item["thumbnailUrl"].startswith("/api/media-thumbnail?")
        assert "type" not in item

    assert done_line["type"] == "done"
    assert done_line["count"] == 2


def test_stream_media_items_rejects_unknown_path(tmp_path: Path) -> None:
    """The stream endpoint must reject paths outside configured review roots."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(tmp_path / "not-configured")},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Path is not configured as a known review path."}


def test_stream_media_items_excludes_hidden_directories(tmp_path: Path) -> None:
    """The stream endpoint must not yield files inside hidden directories."""

    import json

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    review_directory.mkdir(parents=True)

    Image.new("RGB", (8, 8)).save(review_directory / "real.jpg")

    thumb_dir = review_directory / ".thumbnails" / "large"
    thumb_dir.mkdir(parents=True)
    Image.new("RGB", (256, 256)).save(thumb_dir / "abc123.png")

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

    response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "20"},
    )

    assert response.status_code == 200
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    item_lines = lines[:-1]
    names = [json.loads(ln)["name"] for ln in item_lines]
    assert names == ["real.jpg"]
    assert "abc123.png" not in names


def test_stream_media_items_offset_pagination(tmp_path: Path) -> None:
    """Offset pagination should skip the first N media items deterministically."""

    import json

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    review_directory.mkdir(parents=True)

    # Create three images with sortable names so order is predictable
    Image.new("RGB", (8, 8)).save(review_directory / "img_01.jpg")
    Image.new("RGB", (8, 8)).save(review_directory / "img_02.jpg")
    Image.new("RGB", (8, 8)).save(review_directory / "img_03.jpg")

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

    # First page: offset=0, limit=2 → img_01, img_02
    first_response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "2", "offset": "0"},
    )
    first_lines = [ln for ln in first_response.data.decode().splitlines() if ln.strip()]
    first_names = [json.loads(ln)["name"] for ln in first_lines[:-1]]
    first_done = json.loads(first_lines[-1])

    assert first_names == ["img_01.jpg", "img_02.jpg"]
    assert first_done["type"] == "done"
    assert first_done["count"] == 2

    # Second page: offset=2, limit=2 → img_03 only (count < limit → no more pages)
    second_response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "2", "offset": "2"},
    )
    second_lines = [ln for ln in second_response.data.decode().splitlines() if ln.strip()]
    second_names = [json.loads(ln)["name"] for ln in second_lines[:-1]]
    second_done = json.loads(second_lines[-1])

    assert second_names == ["img_03.jpg"]
    assert second_done["type"] == "done"
    assert second_done["count"] == 1


def _make_stream_client(tmp_path: Path) -> tuple["FlaskClient", Path]:
    """Create a test Flask client with a single review directory."""
    import json as _json  # noqa: F401 — callers use json directly

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    review_directory.mkdir(parents=True)

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
    return app.test_client(), review_directory


def test_stream_status_filter_unseen(tmp_path: Path) -> None:
    """statusFilter=unseen must return only items without a .seen companion file."""

    import json

    client, review_directory = _make_stream_client(tmp_path)

    Image.new("RGB", (8, 8)).save(review_directory / "seen.jpg")
    (review_directory / "seen.jpg.seen").write_text("", encoding="utf-8")
    Image.new("RGB", (8, 8)).save(review_directory / "unseen.jpg")

    response = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "10",
            "statusFilter": "unseen",
        },
    )

    assert response.status_code == 200
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    item_names = [json.loads(ln)["name"] for ln in lines[:-1]]
    assert item_names == ["unseen.jpg"]


def test_stream_status_filter_seen(tmp_path: Path) -> None:
    """statusFilter=seen must return only items with a .seen companion file."""

    import json

    client, review_directory = _make_stream_client(tmp_path)

    Image.new("RGB", (8, 8)).save(review_directory / "seen.jpg")
    (review_directory / "seen.jpg.seen").write_text("", encoding="utf-8")
    Image.new("RGB", (8, 8)).save(review_directory / "unseen.jpg")

    response = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "10",
            "statusFilter": "seen",
        },
    )

    assert response.status_code == 200
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    item_names = [json.loads(ln)["name"] for ln in lines[:-1]]
    assert item_names == ["seen.jpg"]


def test_stream_status_filter_locked(tmp_path: Path) -> None:
    """statusFilter=locked must return only items with a .lock companion file."""

    import json

    client, review_directory = _make_stream_client(tmp_path)

    Image.new("RGB", (8, 8)).save(review_directory / "locked.jpg")
    (review_directory / "locked.jpg.lock").write_text("", encoding="utf-8")
    Image.new("RGB", (8, 8)).save(review_directory / "unlocked.jpg")

    response = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "10",
            "statusFilter": "locked",
        },
    )

    assert response.status_code == 200
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    item_names = [json.loads(ln)["name"] for ln in lines[:-1]]
    assert item_names == ["locked.jpg"]


def test_stream_status_filter_trashed(tmp_path: Path) -> None:
    """statusFilter=trashed must return only items inside a .trash/ directory."""

    import json

    client, review_directory = _make_stream_client(tmp_path)

    trash_dir = review_directory / ".trash"
    trash_dir.mkdir()
    Image.new("RGB", (8, 8)).save(trash_dir / "trashed.jpg")
    Image.new("RGB", (8, 8)).save(review_directory / "kept.jpg")

    response = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "10",
            "statusFilter": "trashed",
        },
    )

    assert response.status_code == 200
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    item_names = [json.loads(ln)["name"] for ln in lines[:-1]]
    assert item_names == ["trashed.jpg"]


def test_stream_status_filter_invalid(tmp_path: Path) -> None:
    """An unrecognised statusFilter value must be rejected with 400."""

    client, review_directory = _make_stream_client(tmp_path)

    response = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "10",
            "statusFilter": "bogus",
        },
    )

    assert response.status_code == 400
    assert "statusFilter" in response.get_json()["error"]


def test_stream_status_filter_unseen_respects_limit_and_offset(tmp_path: Path) -> None:
    """statusFilter=unseen pagination: limit and offset apply only to matching items."""

    import json

    client, review_directory = _make_stream_client(tmp_path)

    # Three unseen, one seen — the seen one must never appear
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        Image.new("RGB", (8, 8)).save(review_directory / name)
    Image.new("RGB", (8, 8)).save(review_directory / "d_seen.jpg")
    (review_directory / "d_seen.jpg.seen").write_text("", encoding="utf-8")

    # Page 1: offset=0, limit=2 → a, b
    r1 = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "2",
            "offset": "0",
            "statusFilter": "unseen",
        },
    )
    lines1 = [ln for ln in r1.data.decode().splitlines() if ln.strip()]
    assert [json.loads(ln)["name"] for ln in lines1[:-1]] == ["a.jpg", "b.jpg"]
    assert json.loads(lines1[-1])["type"] == "done"
    assert json.loads(lines1[-1])["count"] == 2

    # Page 2: offset=2, limit=2 → c only (d_seen excluded by filter)
    r2 = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "2",
            "offset": "2",
            "statusFilter": "unseen",
        },
    )
    lines2 = [ln for ln in r2.data.decode().splitlines() if ln.strip()]
    assert [json.loads(ln)["name"] for ln in lines2[:-1]] == ["c.jpg"]
    assert json.loads(lines2[-1])["type"] == "done"
    assert json.loads(lines2[-1])["count"] == 1


# ---------------------------------------------------------------------------
# Cursor-based pagination (after= query parameter)
# ---------------------------------------------------------------------------


def test_stream_cursor_pagination_done_event_contains_last_path(tmp_path: Path) -> None:
    """The 'done' event must include 'lastPath' set to the last yielded item's path."""

    import json

    client, review_directory = _make_stream_client(tmp_path)
    Image.new("RGB", (8, 8)).save(review_directory / "img_a.jpg")
    Image.new("RGB", (8, 8)).save(review_directory / "img_b.jpg")

    response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "10"},
    )
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    done = json.loads(lines[-1])

    assert done["type"] == "done"
    assert done["count"] == 2
    assert done["lastPath"] is not None
    assert done["lastPath"].endswith("img_b.jpg")


def test_stream_cursor_pagination_resumes_after_cursor(tmp_path: Path) -> None:
    """The 'after' cursor must resume the scan from just after the cursor path."""

    import json

    client, review_directory = _make_stream_client(tmp_path)
    for name in ("p1.jpg", "p2.jpg", "p3.jpg"):
        Image.new("RGB", (8, 8)).save(review_directory / name)

    # Page 1: get first 2 items and record the cursor.
    r1 = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "2"},
    )
    lines1 = [ln for ln in r1.data.decode().splitlines() if ln.strip()]
    cursor = json.loads(lines1[-1])["lastPath"]
    assert cursor is not None

    # Page 2: pass cursor as 'after'; must return exactly p3.jpg.
    r2 = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "2",
            "after": cursor,
        },
    )
    lines2 = [ln for ln in r2.data.decode().splitlines() if ln.strip()]
    names2 = [json.loads(ln)["name"] for ln in lines2[:-1]]
    done2 = json.loads(lines2[-1])

    assert names2 == ["p3.jpg"]
    assert done2["type"] == "done"
    assert done2["count"] == 1


def test_stream_cursor_pagination_no_gap_when_items_reviewed_between_pages(
    tmp_path: Path,
) -> None:
    """Cursor pagination must not skip items even when the user reviews items between pages.

    This is the core regression test for the offset-based gap bug: with offset=N
    and statusFilter=unseen, marking items seen between pages shifts the
    'unseen' boundary and causes items to be dropped.  The cursor approach
    tracks filesystem position, not filter-subset position, so it is immune.
    """

    import json

    client, review_directory = _make_stream_client(tmp_path)
    for name in ("f01.jpg", "f02.jpg", "f03.jpg", "f04.jpg", "f05.jpg"):
        Image.new("RGB", (8, 8)).save(review_directory / name)

    # Page 1: 2 unseen items.
    r1 = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "2",
            "statusFilter": "unseen",
        },
    )
    lines1 = [ln for ln in r1.data.decode().splitlines() if ln.strip()]
    assert [json.loads(ln)["name"] for ln in lines1[:-1]] == ["f01.jpg", "f02.jpg"]
    cursor = json.loads(lines1[-1])["lastPath"]

    # Simulate user reviewing: mark both page-1 items as seen.
    (review_directory / "f01.jpg.seen").write_text("", encoding="utf-8")
    (review_directory / "f02.jpg.seen").write_text("", encoding="utf-8")

    # Page 2 with cursor: must return f03, f04 (NOT skip them due to seen f01/f02).
    r2 = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "2",
            "statusFilter": "unseen",
            "after": cursor,
        },
    )
    lines2 = [ln for ln in r2.data.decode().splitlines() if ln.strip()]
    names2 = [json.loads(ln)["name"] for ln in lines2[:-1]]

    # f03 and f04 must be returned; they must not be skipped.
    assert names2 == ["f03.jpg", "f04.jpg"]


def test_stream_cursor_done_event_last_path_is_null_when_no_items(tmp_path: Path) -> None:
    """The 'lastPath' field in the done event must be null when no items are yielded."""

    import json

    client, review_directory = _make_stream_client(tmp_path)
    # No media files — only a non-media file.
    (review_directory / "readme.txt").write_text("x", encoding="utf-8")

    response = client.get(
        "/api/media-items/stream",
        query_string={"path": str(review_directory.resolve()), "limit": "10"},
    )
    lines = [ln for ln in response.data.decode().splitlines() if ln.strip()]
    done = json.loads(lines[-1])

    assert done["type"] == "done"
    assert done["count"] == 0
    assert done["lastPath"] is None


def test_stream_cursor_after_outside_path_rejected(tmp_path: Path) -> None:
    """The 'after' parameter must be rejected when it points outside the review path."""

    client, review_directory = _make_stream_client(tmp_path)

    response = client.get(
        "/api/media-items/stream",
        query_string={
            "path": str(review_directory.resolve()),
            "limit": "10",
            "after": "/etc/passwd",
        },
    )

    assert response.status_code == 400
    assert "after" in response.get_json()["error"].lower()


