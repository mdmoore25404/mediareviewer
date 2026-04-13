"""Filesystem scanner for image and video review items."""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".bmp",
        ".gif",
        ".jpeg",
        ".jpg",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
    },
)

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".avi",
        ".m4v",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".mts",
        ".m2ts",
        ".wmv",
    },
)

COMPANION_SUFFIXES: frozenset[str] = frozenset({".lock", ".trash", ".seen"})


@dataclass(frozen=True, slots=True)
class MediaStatus:
    """Companion-file status flags for a single media item."""

    locked: bool
    trashed: bool
    seen: bool


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    """Optional metadata derived from media probing."""

    width: int | None
    height: int | None


@dataclass(frozen=True, slots=True)
class MediaItem:
    """Typed media item returned by the scan endpoint."""

    path: str
    name: str
    media_type: str
    size_bytes: int
    modified_at: str
    created_at: str
    status: MediaStatus
    metadata: MediaMetadata

    def to_payload(self) -> dict[str, object]:
        """Convert the media item to a JSON-friendly dictionary."""

        payload = asdict(self)
        payload["mediaType"] = payload.pop("media_type")
        payload["sizeBytes"] = payload.pop("size_bytes")
        payload["modifiedAt"] = payload.pop("modified_at")
        payload["createdAt"] = payload.pop("created_at")
        return payload


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Result of scanning a review folder for media files."""

    items: tuple[MediaItem, ...]
    ignored_count: int


@dataclass(frozen=True, slots=True)
class FolderInfo:
    """Information about a folder."""

    path: str
    name: str
    has_children: bool

class MediaScanner:
    """Scan a folder recursively and return supported media files only."""

    def scan(self, root_path: Path, limit: int) -> ScanResult:
        """Recursively scan for image/video files up to a configured limit."""

        items: list[MediaItem] = []
        ignored_count = 0
        normalized_root = root_path.expanduser().resolve()

        for candidate in sorted(normalized_root.rglob("*")):
            if not candidate.is_file():
                continue
            if self._is_companion_file(candidate):
                ignored_count += 1
                continue

            media_type = self._detect_media_type(candidate)
            if media_type is None:
                ignored_count += 1
                continue

            items.append(self._build_media_item(candidate, media_type))
            if len(items) >= limit:
                break

        return ScanResult(items=tuple(items), ignored_count=ignored_count)

    def scan_folder(
        self, folder_path: Path, offset: int = 0, limit: int = 100
    ) -> ScanResult:
        """Scan a single folder (not recursive) with pagination support."""

        items: list[MediaItem] = []
        ignored_count = 0
        normalized_folder = folder_path.expanduser().resolve()

        if not normalized_folder.is_dir():
             return ScanResult(items=(), ignored_count=0)

        all_files = [
            f
            for f in sorted(normalized_folder.iterdir())
            if f.is_file() and not self._is_companion_file(f)
        ]

        for candidate in all_files[offset : offset + limit]:
            media_type = self._detect_media_type(candidate)
            if media_type is None:
                ignored_count += 1
                continue

            items.append(self._build_media_item(candidate, media_type))

        return ScanResult(items=tuple(items), ignored_count=ignored_count)

    def get_folders(self, parent_path: Path) -> tuple[FolderInfo, ...]:
        """Get sorted list of immediate child folders."""

        normalized_parent = parent_path.expanduser().resolve()
        if not normalized_parent.is_dir():
             return ()

        folders: list[FolderInfo] = []
        for item in sorted(normalized_parent.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                has_children = any(
                    child.is_dir() and not child.name.startswith(".")
                    for child in item.iterdir()
                )
                folders.append(
                    FolderInfo(path=str(item), name=item.name, has_children=has_children)
                )

        return tuple(folders)

    def _detect_media_type(self, file_path: Path) -> str | None:
        suffix = file_path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in VIDEO_EXTENSIONS:
            return "video"
        return None

    def _is_companion_file(self, file_path: Path) -> bool:
        lower_path = str(file_path).lower()
        return any(lower_path.endswith(suffix) for suffix in COMPANION_SUFFIXES)

    def _build_media_item(self, file_path: Path, media_type: str) -> MediaItem:
        file_stat = file_path.stat()
        return MediaItem(
            path=str(file_path),
            name=file_path.name,
            media_type=media_type,
            size_bytes=file_stat.st_size,
            modified_at=self._to_iso8601(file_stat.st_mtime),
            created_at=self._to_iso8601(file_stat.st_ctime),
            status=MediaStatus(
                locked=file_path.with_suffix(f"{file_path.suffix}.lock").exists(),
                trashed=file_path.with_suffix(f"{file_path.suffix}.trash").exists(),
                seen=file_path.with_suffix(f"{file_path.suffix}.seen").exists(),
            ),
            metadata=self._probe_metadata(file_path, media_type),
        )

    def _probe_metadata(self, file_path: Path, media_type: str) -> MediaMetadata:
        if media_type != "image":
            return MediaMetadata(width=None, height=None)

        try:
            with Image.open(file_path) as image:
                width, height = image.size
                return MediaMetadata(width=width, height=height)
        except (OSError, UnidentifiedImageError):
            return MediaMetadata(width=None, height=None)

    def _to_iso8601(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
