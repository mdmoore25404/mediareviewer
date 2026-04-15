"""Filesystem scanner for image and video review items."""

import logging
import os
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

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

# DCF (Design rule for Camera File system) subdirectory names are three decimal
# digits followed by one to five alphanumeric/underscore characters, e.g.
# ``100MEDIA``, ``101GOPRO``, ``102_PANO``.
DCIM_SUBDIR_PATTERN: re.Pattern[str] = re.compile(r"^\d{3}[A-Za-z0-9_]+$")

StatusFilter = Literal["all", "unseen", "seen", "locked", "trashed"]

_log = logging.getLogger(__name__)


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


def is_dcim_path(root: Path) -> bool:
    """Return True when *root* follows DCF/DCIM directory conventions.

    Accepts three forms commonly found on trail-cam and digital-camera SD cards:

    1. The path is itself named ``DCIM`` and contains at least one numbered
       subdirectory (e.g. ``100MEDIA``).
    2. The path is a numbered DCIM subdirectory sitting directly inside a
       ``DCIM`` parent (e.g. ``…/DCIM/100MEDIA``).
    3. The path contains an immediate child directory named ``DCIM`` which
       itself contains numbered subdirectories.
    """
    # Case 1: path IS the DCIM root
    if root.name.upper() == "DCIM":
        try:
            return any(
                c.is_dir() and DCIM_SUBDIR_PATTERN.match(c.name)
                for c in root.iterdir()
            )
        except PermissionError:
            return False

    # Case 2: path is a numbered DCIM subdir (e.g. 100MEDIA inside DCIM/)
    if DCIM_SUBDIR_PATTERN.match(root.name) and root.parent.name.upper() == "DCIM":
        return True

    # Case 3: path contains an immediate DCIM child with numbered subdirs
    dcim_child = root / "DCIM"
    if dcim_child.is_dir():
        try:
            return any(
                c.is_dir() and DCIM_SUBDIR_PATTERN.match(c.name)
                for c in dcim_child.iterdir()
            )
        except PermissionError:
            return False

    return False


def _sorted_walk(root: Path) -> Iterator[Path]:
    """Yield every file under *root* in lexicographic path order incrementally.

    Uses ``os.walk`` instead of ``sorted(root.rglob('*'))`` so that results
    start arriving before the entire directory tree has been traversed.
    Hidden directories (names beginning with ``'.'``) are pruned before
    descending so they are never entered at all.
    """
    for dirpath, dirnames, filenames in os.walk(str(root)):
        # Prune hidden dirs in-place; os.walk respects this before recursing.
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for filename in sorted(filenames):
            yield Path(dirpath) / filename


def _iter_candidates(root: Path) -> Iterator[Path]:
    """Return a path iterator appropriate for *root*.

    For DCIM-structured roots the incremental :func:`_sorted_walk` is used so
    that the first scanned items are delivered to callers without waiting for
    the whole directory tree to be materialised.  For other roots the
    traditional ``sorted(root.rglob('*'))`` approach is used to preserve the
    existing global-sort behaviour.
    """
    if is_dcim_path(root):
        _log.debug("DCIM structure detected at %s — using incremental walk", root)
        return _sorted_walk(root)
    return iter(sorted(root.rglob("*")))


class MediaScanner:
    """Scan a folder recursively and return supported media files only."""

    def scan(self, root_path: Path, limit: int) -> ScanResult:
        """Recursively scan for image/video files up to a configured limit."""

        items: list[MediaItem] = []
        ignored_count = 0
        normalized_root = root_path.expanduser().resolve()

        for candidate in _iter_candidates(normalized_root):
            if not candidate.is_file():
                continue
            if self._is_in_hidden_directory(candidate, normalized_root):
                ignored_count += 1
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

    def scan_stream(
        self, root_path: Path, limit: int, offset: int = 0, status_filter: StatusFilter = "all"
    ) -> Iterator[MediaItem]:
        """Yield media items one at a time as they are discovered, up to *limit*.

        *offset* media items that pass the *status_filter* (and would otherwise
        be yielded) are skipped first, enabling page-based pagination.
        *status_filter* is applied on the filesystem before counting against
        *offset* or *limit*, so every page contains only matching items.

        - ``"all"``    — no filtering; return every media file.
        - ``"unseen"`` — items without a ``.seen`` companion file.
        - ``"seen"``   — items with a ``.seen`` companion file.
        - ``"locked"`` — items with a ``.lock`` companion file.
        - ``"trashed"``— items with a ``.trash`` companion file.

        Hidden directories (names starting with ``'.'``) and companion files are
        skipped silently and do **not** count against *offset* or *limit*.
        """

        normalized_root = root_path.expanduser().resolve()
        skipped = 0
        count = 0
        for candidate in _iter_candidates(normalized_root):
            if not candidate.is_file():
                continue
            if self._is_in_hidden_directory(candidate, normalized_root):
                continue
            if self._is_companion_file(candidate):
                continue
            media_type = self._detect_media_type(candidate)
            if media_type is None:
                continue
            if not self._matches_status_filter(candidate, status_filter):
                continue
            if skipped < offset:
                skipped += 1
                continue
            yield self._build_media_item(candidate, media_type)
            count += 1
            if count >= limit:
                break

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
        """Get sorted list of immediate child folders.

        Directories that cannot be read due to permission restrictions are
        silently skipped rather than raising a 500 error to the caller.
        """

        normalized_parent = parent_path.expanduser().resolve()
        if not normalized_parent.is_dir():
            return ()

        try:
            entries = sorted(normalized_parent.iterdir())
        except PermissionError:
            return ()

        folders: list[FolderInfo] = []
        for item in entries:
            if not item.is_dir() or item.name.startswith("."):
                continue
            try:
                has_children = any(
                    child.is_dir() and not child.name.startswith(".")
                    for child in item.iterdir()
                )
            except PermissionError:
                has_children = False
            folders.append(
                FolderInfo(path=str(item), name=item.name, has_children=has_children)
            )

        return tuple(folders)

    def _matches_status_filter(self, file_path: Path, status_filter: StatusFilter) -> bool:
        """Return True if *file_path* satisfies the requested status filter."""
        if status_filter == "all":
            return True
        lock_exists = file_path.with_suffix(f"{file_path.suffix}.lock").exists()
        trash_exists = file_path.with_suffix(f"{file_path.suffix}.trash").exists()
        seen_exists = file_path.with_suffix(f"{file_path.suffix}.seen").exists()
        if status_filter == "unseen":
            return not seen_exists
        if status_filter == "seen":
            return seen_exists
        if status_filter == "locked":
            return lock_exists
        if status_filter == "trashed":
            return trash_exists
        return True  # unreachable but satisfies exhaustiveness

    def _detect_media_type(self, file_path: Path) -> str | None:
        suffix = file_path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in VIDEO_EXTENSIONS:
            return "video"
        return None

    def _is_in_hidden_directory(self, file_path: Path, root: Path) -> bool:
        """Return True if any directory component between root and file_path starts with '.'."""
        try:
            rel = file_path.relative_to(root)
        except ValueError:
            return False
        return any(part.startswith(".") for part in rel.parts[:-1])

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
