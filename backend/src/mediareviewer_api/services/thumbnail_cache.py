"""On-disk thumbnail cache compatible with Linux desktop thumbnail conventions."""

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, PngImagePlugin, UnidentifiedImageError

from mediareviewer_api.services.media_scanner import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS


@dataclass(frozen=True, slots=True)
class ThumbnailResult:
    """Result of locating or generating a thumbnail on disk."""

    file_path: Path
    was_generated: bool


class ThumbnailCacheService:
    """Find or create cached thumbnails for supported media files.
    
    Thumbnails are stored within each mounted review path at .thumbnails directory
    to enable different tool instances to share the cache and benefit from
    local-only thumbnail storage.
    """

    def ensure_thumbnail(self, media_path: Path, review_path: Path, size: int) -> ThumbnailResult:
        """Return a cached thumbnail path, generating it on disk when needed.
        
        Args:
            media_path: The media file to generate a thumbnail for.
            review_path: The root of the mounted review folder.
            size: The desired thumbnail size in pixels.
        """

        normalized_path = media_path.expanduser().resolve()
        normalized_review = review_path.expanduser().resolve()
        cache_root = normalized_review / ".thumbnails"
        thumbnail_path = self._thumbnail_path_for_media(normalized_path, cache_root, size)
        if self._is_current_thumbnail(thumbnail_path, normalized_path):
            return ThumbnailResult(file_path=thumbnail_path, was_generated=False)

        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        media_type = self._detect_media_type(normalized_path)
        if media_type == "image":
            self._generate_image_thumbnail(normalized_path, thumbnail_path, size)
        elif media_type == "video":
            success = self._generate_video_thumbnail_ffmpeg(normalized_path, thumbnail_path, size)
            if not success:
                self._generate_placeholder_thumbnail(
                    normalized_path, thumbnail_path, size, media_type
                )
        else:
            self._generate_placeholder_thumbnail(
                normalized_path, thumbnail_path, size, media_type
            )
        return ThumbnailResult(file_path=thumbnail_path, was_generated=True)

    def delete_thumbnail(self, media_path: Path, review_path: Path) -> None:
        """Remove cached thumbnails for a media file.
        
        Args:
            media_path: The media file to delete thumbnails for.
            review_path: The root of the mounted review folder.
        """
        normalized_path = media_path.expanduser().resolve()
        normalized_review = review_path.expanduser().resolve()
        cache_root = normalized_review / ".thumbnails"
        for size in [128, 256, 512]:
            thumbnail_path = self._thumbnail_path_for_media(normalized_path, cache_root, size)
            if thumbnail_path.exists():
                thumbnail_path.unlink()



    def _thumbnail_path_for_media(self, media_path: Path, cache_root: Path, size: int) -> Path:
        cache_dir_name = "large" if size > 128 else "normal"
        media_uri = media_path.as_uri()
        digest = hashlib.md5(media_uri.encode("utf-8"), usedforsecurity=False).hexdigest()
        file_name = f"{digest}.png"
        return cache_root / cache_dir_name / file_name

    def _is_current_thumbnail(self, thumbnail_path: Path, media_path: Path) -> bool:
        if not thumbnail_path.exists():
            return False
        return thumbnail_path.stat().st_mtime >= media_path.stat().st_mtime

    def _detect_media_type(self, media_path: Path) -> str:
        suffix = media_path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in VIDEO_EXTENSIONS:
            return "video"
        return "file"

    def _generate_image_thumbnail(self, media_path: Path, thumbnail_path: Path, size: int) -> None:
        try:
            with Image.open(media_path) as image:
                thumbnail = ImageOps.exif_transpose(image.convert("RGB"))
                thumbnail.thumbnail((size, size), Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (size, size), color=(237, 243, 246))
                offset_x = (size - thumbnail.width) // 2
                offset_y = (size - thumbnail.height) // 2
                canvas.paste(thumbnail, (offset_x, offset_y))
                self._save_thumbnail_png(canvas, thumbnail_path, media_path)
        except (OSError, UnidentifiedImageError):
            self._generate_placeholder_thumbnail(media_path, thumbnail_path, size, "image")

    def _generate_video_thumbnail_ffmpeg(
        self,
        media_path: Path,
        thumbnail_path: Path,
        size: int,
    ) -> bool:
        """Extract a frame from a video using ffmpeg. Returns True if successful."""
        try:
            temp_frame = thumbnail_path.parent / f"{thumbnail_path.stem}_frame.jpg"
            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    str(media_path),
                    "-ss",
                    "00:00:02",
                    "-vframes",
                    "1",
                    "-vf",
                    f"scale={size}:{size}:force_original_aspect_ratio=decrease,pad={size}:{size}:(ow-iw)/2:(oh-ih)/2:color=black",
                    str(temp_frame),
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )
            with Image.open(temp_frame) as frame:
                canvas = Image.new("RGB", (size, size), color=(0, 0, 0))
                canvas.paste(frame, ((size - frame.width) // 2, (size - frame.height) // 2))
                self._save_thumbnail_png(canvas, thumbnail_path, media_path)
            temp_frame.unlink()
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return False


    def _generate_placeholder_thumbnail(
        self,
        media_path: Path,
        thumbnail_path: Path,
        size: int,
        media_type: str,
    ) -> None:
        background = (24, 35, 52) if media_type == "video" else (109, 124, 140)
        foreground = (244, 246, 248)
        canvas = Image.new("RGB", (size, size), color=background)
        draw = ImageDraw.Draw(canvas)
        label = media_type.upper()
        extension_label = media_path.suffix.upper().removeprefix(".")
        draw.rounded_rectangle(
            (18, 18, size - 18, size - 18),
            radius=18,
            outline=(255, 255, 255),
            width=2,
        )
        draw.text((28, size // 2 - 18), label, fill=foreground)
        draw.text((28, size // 2 + 8), extension_label or "FILE", fill=foreground)
        self._save_thumbnail_png(canvas, thumbnail_path, media_path)

    def _save_thumbnail_png(
        self,
        image: Image.Image,
        thumbnail_path: Path,
        media_path: Path,
    ) -> None:
        png_info = PngImagePlugin.PngInfo()
        png_info.add_text("Thumb::URI", media_path.as_uri())
        png_info.add_text("Thumb::MTime", str(int(media_path.stat().st_mtime)))
        png_info.add_text("Software", "mediareviewer")
        image.save(thumbnail_path, format="PNG", pnginfo=png_info)
        os.utime(thumbnail_path, (media_path.stat().st_mtime, media_path.stat().st_mtime))
