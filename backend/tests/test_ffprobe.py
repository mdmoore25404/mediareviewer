"""Tests for _probe_video_metadata ffprobe integration."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from mediareviewer_api.services.media_scanner import (
    MediaMetadata,
    MediaScanner,
    _probe_video_metadata,
)

# ---------------------------------------------------------------------------
# _probe_video_metadata — ffprobe not available
# ---------------------------------------------------------------------------


def test_probe_video_metadata_returns_none_when_ffprobe_missing(
    tmp_path: Path,
) -> None:
    """When ffprobe is absent from PATH, all fields are None."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value=None,
    ):
        result = _probe_video_metadata(video)

    assert result == MediaMetadata(width=None, height=None, duration_seconds=None)


# ---------------------------------------------------------------------------
# _probe_video_metadata — subprocess errors
# ---------------------------------------------------------------------------


def test_probe_video_metadata_returns_none_on_timeout(tmp_path: Path) -> None:
    """A subprocess.TimeoutExpired is swallowed and all fields are None."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value="/usr/bin/ffprobe",
    ):
        with patch(
            "mediareviewer_api.services.media_scanner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=5),
        ):
            result = _probe_video_metadata(video)

    assert result == MediaMetadata(width=None, height=None, duration_seconds=None)


def test_probe_video_metadata_returns_none_on_oserror(tmp_path: Path) -> None:
    """An OSError from subprocess.run is swallowed and all fields are None."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value="/usr/bin/ffprobe",
    ):
        with patch(
            "mediareviewer_api.services.media_scanner.subprocess.run",
            side_effect=OSError("exec failed"),
        ):
            result = _probe_video_metadata(video)

    assert result == MediaMetadata(width=None, height=None, duration_seconds=None)


# ---------------------------------------------------------------------------
# _probe_video_metadata — JSON parsing
# ---------------------------------------------------------------------------


def _make_ffprobe_result(stdout: bytes) -> MagicMock:
    """Return a mock subprocess.CompletedProcess with the given stdout bytes."""
    proc = MagicMock()
    proc.stdout = stdout
    return proc


def test_probe_video_metadata_parses_valid_output(tmp_path: Path) -> None:
    """Valid ffprobe output populates width, height, and duration_seconds."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    ffprobe_output = json.dumps(
        {
            "streams": [{"width": 1920, "height": 1080}],
            "format": {"duration": "63.5"},
        }
    ).encode()

    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value="/usr/bin/ffprobe",
    ):
        with patch(
            "mediareviewer_api.services.media_scanner.subprocess.run",
            return_value=_make_ffprobe_result(ffprobe_output),
        ):
            result = _probe_video_metadata(video)

    assert result.width == 1920
    assert result.height == 1080
    assert result.duration_seconds == 63.5


def test_probe_video_metadata_returns_none_on_invalid_json(tmp_path: Path) -> None:
    """Unparseable ffprobe output returns all-None metadata."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value="/usr/bin/ffprobe",
    ):
        with patch(
            "mediareviewer_api.services.media_scanner.subprocess.run",
            return_value=_make_ffprobe_result(b"not json"),
        ):
            result = _probe_video_metadata(video)

    assert result == MediaMetadata(width=None, height=None, duration_seconds=None)


def test_probe_video_metadata_handles_empty_streams(tmp_path: Path) -> None:
    """Audio-only output (no video stream) yields None width/height but may have duration."""
    video = tmp_path / "audio.mp4"
    video.write_bytes(b"fake")

    ffprobe_output = json.dumps(
        {
            "streams": [],
            "format": {"duration": "120.0"},
        }
    ).encode()

    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value="/usr/bin/ffprobe",
    ):
        with patch(
            "mediareviewer_api.services.media_scanner.subprocess.run",
            return_value=_make_ffprobe_result(ffprobe_output),
        ):
            result = _probe_video_metadata(video)

    assert result.width is None
    assert result.height is None
    assert result.duration_seconds == 120.0


def test_probe_video_metadata_handles_missing_duration(tmp_path: Path) -> None:
    """ffprobe output with a stream but no format.duration leaves duration_seconds None."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    ffprobe_output = json.dumps(
        {
            "streams": [{"width": 640, "height": 480}],
            "format": {},
        }
    ).encode()

    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value="/usr/bin/ffprobe",
    ):
        with patch(
            "mediareviewer_api.services.media_scanner.subprocess.run",
            return_value=_make_ffprobe_result(ffprobe_output),
        ):
            result = _probe_video_metadata(video)

    assert result.width == 640
    assert result.height == 480
    assert result.duration_seconds is None


# ---------------------------------------------------------------------------
# MediaScanner — dispatch via _probe_metadata
# ---------------------------------------------------------------------------


def test_media_scanner_calls_ffprobe_for_video(tmp_path: Path) -> None:
    """MediaScanner._probe_metadata routes video files through _probe_video_metadata."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")

    ffprobe_output = json.dumps(
        {
            "streams": [{"width": 1280, "height": 720}],
            "format": {"duration": "30.0"},
        }
    ).encode()

    scanner = MediaScanner()
    with patch(
        "mediareviewer_api.services.media_scanner.shutil.which",
        return_value="/usr/bin/ffprobe",
    ):
        with patch(
            "mediareviewer_api.services.media_scanner.subprocess.run",
            return_value=_make_ffprobe_result(ffprobe_output),
        ):
            meta = scanner._probe_metadata(video, "video")  # noqa: SLF001

    assert meta.width == 1280
    assert meta.height == 720
    assert meta.duration_seconds == 30.0


def test_media_scanner_does_not_call_ffprobe_for_images(tmp_path: Path) -> None:
    """MediaScanner._probe_metadata never calls ffprobe for image files."""
    from PIL import Image

    img_path = tmp_path / "photo.jpg"
    img = Image.new("RGB", (100, 80))
    img.save(img_path)

    scanner = MediaScanner()
    with patch(
        "mediareviewer_api.services.media_scanner.subprocess.run",
    ) as mock_run:
        meta = scanner._probe_metadata(img_path, "image")  # noqa: SLF001

    mock_run.assert_not_called()
    assert meta.width == 100
    assert meta.height == 80
    assert meta.duration_seconds is None
