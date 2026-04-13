"""On-disk thumbnail cache compatible with Linux desktop thumbnail conventions."""

import hashlib
import os
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
    """Find or create cached thumbnails for supported media files."""

    def __init__(self, cache_root: Path) -> None:
        self._cache_root = cache_root.expanduser()

    def ensure_thumbnail(self, media_path: Path, size: int) -> ThumbnailResult:
        """Return a cached thumbnail path, generating it on disk when needed."""

        normalized_path = media_path.expanduser().resolve()
        thumbnail_path = self._thumbnail_path_for_media(normalized_path, size)
        if self._is_current_thumbnail(thumbnail_path, normalized_path):
            return ThumbnailResult(file_path=thumbnail_path, was_generated=False)

        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        media_type = self._detect_media_type(normalized_path)
        if media_type == "image":
            self._generate_image_thumbnail(normalized_path, thumbnail_path, size)
        else:
            self._generate_placeholder_thumbnail(normalized_path, thumbnail_path, size, media_type)
        return ThumbnailResult(file_path=thumbnail_path, was_generated=True)

    def _thumbnail_path_for_media(self, media_path: Path, size: int) -> Path:
        cache_dir_name = "large" if size > 128 else "normal"
        media_uri = media_path.as_uri()
        digest = hashlib.md5(media_uri.encode("utf-8"), usedforsecurity=False).hexdigest()
        file_name = f"{digest}.png"
        return self._cache_root / cache_dir_name / file_name

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
