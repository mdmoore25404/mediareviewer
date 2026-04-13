"""Tests for recursive media scanning endpoints."""

from pathlib import Path

from flask.testing import FlaskClient
from PIL import Image

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def test_media_items_returns_supported_files_and_status(tmp_path: Path) -> None:
    """The media endpoint should return image/video files and ignore unrelated files."""

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
        "/api/media-items",
        query_string={"path": str(review_directory.resolve()), "limit": "20"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["path"] == str(review_directory.resolve())
    assert payload["count"] == 2
    assert payload["ignoredCount"] >= 2

    item_names = {item["name"] for item in payload["items"]}
    assert item_names == {"frame001.jpg", "clip001.mp4"}

    image_item = next(item for item in payload["items"] if item["name"] == "frame001.jpg")
    assert image_item["mediaType"] == "image"
    assert image_item["status"] == {"locked": False, "trashed": False, "seen": True}
    assert image_item["metadata"] == {"width": 12, "height": 8}
    assert image_item["thumbnailUrl"].startswith("/api/media-thumbnail?")

    video_item = next(item for item in payload["items"] if item["name"] == "clip001.mp4")
    assert video_item["mediaType"] == "video"
    assert video_item["status"] == {"locked": True, "trashed": False, "seen": False}
    assert video_item["metadata"] == {"width": None, "height": None}
    assert video_item["thumbnailUrl"].startswith("/api/media-thumbnail?")


def test_media_items_requires_known_path(tmp_path: Path) -> None:
    """Unknown paths should be rejected before scanning."""

    state_directory = tmp_path / "state"
    state_directory.mkdir(parents=True)
    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    unknown_directory = tmp_path / "not-configured"
    unknown_directory.mkdir(parents=True)

    response = client.get(
        "/api/media-items",
        query_string={"path": str(unknown_directory.resolve())},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Path is not configured as a known review path."}


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


def test_media_items_excludes_thumbnails_directory(tmp_path: Path) -> None:
    """The scan endpoint must not return files stored inside hidden directories like .thumbnails."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "trailcam"
    media_dir = review_directory / "DCIM"
    media_dir.mkdir(parents=True)

    real_image = media_dir / "frame001.jpg"
    Image.new("RGB", (12, 8), color=(64, 32, 16)).save(real_image)

    # Simulate generated thumbnails stored under .thumbnails (as ThumbnailCacheService does)
    thumb_dir = review_directory / ".thumbnails" / "large"
    thumb_dir.mkdir(parents=True)
    thumb_png = thumb_dir / "d5c529d2e907d4406b594e03b963dfbe.png"
    Image.new("RGB", (256, 256), color=(0, 0, 0)).save(thumb_png)

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
        "/api/media-items",
        query_string={"path": str(review_directory.resolve()), "limit": "50"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    names = [item["name"] for item in payload["items"]]
    assert names == ["frame001.jpg"]
    assert "d5c529d2e907d4406b594e03b963dfbe.png" not in names


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

    assert done_line == {"type": "done", "count": 2}


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

