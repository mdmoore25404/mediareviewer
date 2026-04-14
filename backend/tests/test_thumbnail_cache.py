"""Unit tests for ThumbnailCacheService."""

from pathlib import Path

from PIL import Image

from mediareviewer_api.services.thumbnail_cache import ThumbnailCacheService


def test_video_placeholder_marked_stale_for_retry(tmp_path: Path) -> None:
    """A video thumbnail that falls back to a placeholder must be saved with
    mtime=0 so that the next request retries ffmpeg rather than serving a
    permanently cached placeholder."""

    svc = ThumbnailCacheService()
    review = tmp_path / "review"
    review.mkdir()
    # Write a file with a .mp4 extension that ffmpeg cannot decode.
    bad_video = review / "broken.mp4"
    bad_video.write_bytes(b"not a real video file")

    result = svc.ensure_thumbnail(bad_video, review, size=128)

    assert result.file_path.exists(), "placeholder PNG must be written to disk"
    assert result.file_path.stat().st_mtime == 0, (
        "placeholder mtime must be 0 so _is_current_thumbnail returns False next call"
    )


def test_retried_video_thumbnail_replaces_placeholder(tmp_path: Path) -> None:
    """The stale-mtime on a placeholder means the next ensure_thumbnail call
    regenerates the thumbnail (was_generated=True) instead of serving the
    cached placeholder."""

    svc = ThumbnailCacheService()
    review = tmp_path / "review"
    review.mkdir()
    bad_video = review / "broken.mp4"
    bad_video.write_bytes(b"not a real video file")

    # First call — ffmpeg fails, placeholder cached with mtime=0.
    first = svc.ensure_thumbnail(bad_video, review, size=128)
    assert first.was_generated

    # Second call — mtime=0 < bad_video.stat().st_mtime, so regeneration runs.
    second = svc.ensure_thumbnail(bad_video, review, size=128)
    assert second.was_generated, (
        "stale mtime must cause a regeneration attempt on every request"
    )


def test_successful_image_thumbnail_not_marked_stale(tmp_path: Path) -> None:
    """A successfully generated image thumbnail must NOT have mtime=0."""

    svc = ThumbnailCacheService()
    review = tmp_path / "review"
    review.mkdir()
    image_file = review / "photo.jpg"
    Image.new("RGB", (64, 64)).save(image_file)

    result = svc.ensure_thumbnail(image_file, review, size=128)

    assert result.was_generated
    assert result.file_path.stat().st_mtime > 0, (
        "a successfully generated thumbnail must keep a non-zero mtime"
    )


def test_prune_orphaned_thumbnails_removes_dead_entries(tmp_path: Path) -> None:
    """Thumbnails whose source media file no longer exists must be pruned."""

    svc = ThumbnailCacheService()
    review = tmp_path / "review"
    review.mkdir()
    image_file = review / "photo.jpg"
    Image.new("RGB", (8, 8)).save(image_file)

    result = svc.ensure_thumbnail(image_file, review, size=128)
    assert result.file_path.exists()

    # Simulate external deletion of the source media file.
    image_file.unlink()

    pruned = svc.prune_orphaned_thumbnails(review)

    assert pruned == 1
    assert not result.file_path.exists()


def test_prune_orphaned_thumbnails_keeps_valid_entries(tmp_path: Path) -> None:
    """Thumbnails whose source file still exists must not be removed."""

    svc = ThumbnailCacheService()
    review = tmp_path / "review"
    review.mkdir()
    image_file = review / "photo.jpg"
    Image.new("RGB", (8, 8)).save(image_file)

    result = svc.ensure_thumbnail(image_file, review, size=128)
    assert result.file_path.exists()

    pruned = svc.prune_orphaned_thumbnails(review)

    assert pruned == 0
    assert result.file_path.exists()


def test_prune_orphaned_thumbnails_no_cache_dir_is_safe(tmp_path: Path) -> None:
    """prune_orphaned_thumbnails must return 0 without error when no cache
    directory exists yet."""

    svc = ThumbnailCacheService()
    review = tmp_path / "review"
    review.mkdir()

    pruned = svc.prune_orphaned_thumbnails(review)

    assert pruned == 0
