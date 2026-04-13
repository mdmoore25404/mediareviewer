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

    video_item = next(item for item in payload["items"] if item["name"] == "clip001.mp4")
    assert video_item["mediaType"] == "video"
    assert video_item["status"] == {"locked": True, "trashed": False, "seen": False}
    assert video_item["metadata"] == {"width": None, "height": None}


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

