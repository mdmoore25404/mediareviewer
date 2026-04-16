"""Filesystem scanner for image and video review items."""

import json
import logging
import os
import re
import shutil
import subprocess
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

COMPANION_SUFFIXES: frozenset[str] = frozenset({".lock", ".seen"})

# DCF (Design rule for Camera File system) subdirectory names are three decimal
# digits followed by one to five alphanumeric/underscore characters, e.g.
# ``100MEDIA``, ``101GOPRO``, ``102_PANO``.
DCIM_SUBDIR_PATTERN: re.Pattern[str] = re.compile(r"^\d{3}[A-Za-z0-9_]+$")

# ---------------------------------------------------------------------------
# In-memory DCIM subtree cache
#
# ``_find_dcim_subtrees`` performs a directory-only ``os.walk`` that can take
# 1–18 s over a network mount.  Subsequent calls for the same root (e.g.
# pagination requests) get an instant cache hit provided neither the root
# directory mtime nor the direct ``DCIM/`` child mtime has changed.
#
# Limitation: subtrees nested deeper than ``<root>/DCIM`` (e.g.
# ``<root>/cam1/DCIM/100MEDIA``) are only re-discovered when the root mtime
# changes.  For trail-camera workloads this is acceptable because the
# directory structure changes infrequently relative to file additions.
# ---------------------------------------------------------------------------

# Key → {"root_mtime": int | None, "dcim_mtime": int | None,
#         "subtrees": list[str]}  (mtimes in nanoseconds)
_dcim_subtree_cache: dict[str, dict[str, object]] = {}


def _dcim_cache_mtimes(root: Path) -> tuple[int | None, int | None]:
    """Return ``(root_mtime_ns, dcim_dir_mtime_ns)`` used to validate the cache for *root*.

    Nanosecond integer timestamps avoid the float-precision loss that ``st_mtime``
    (a double) can introduce for timestamps around 1.7 × 10⁹ seconds.
    """
    try:
        root_mtime: int | None = root.stat().st_mtime_ns
    except OSError:
        root_mtime = None
    dcim_dir = root / "DCIM"
    try:
        dcim_mtime: int | None = dcim_dir.stat().st_mtime_ns if dcim_dir.is_dir() else None
    except OSError:
        dcim_mtime = None
    return root_mtime, dcim_mtime


def _clear_dcim_cache() -> None:
    """Evict all entries from the in-memory DCIM subtree cache.

    Intended for use in tests to prevent cross-test contamination.  Not
    needed in production because each unique ``tmp_path`` is a distinct cache
    key, but useful when a test mutates a directory it has already scanned.
    """
    _dcim_subtree_cache.clear()


StatusFilter = Literal["all", "unseen", "seen", "locked", "trashed"]

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MediaStatus:
    """Companion-file status flags for a single media item."""

    locked: bool
    trashed: bool
    seen: bool


# Timeout (seconds) for a single ffprobe invocation.
_FFPROBE_TIMEOUT: int = 5


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    """Optional metadata derived from media probing."""

    width: int | None
    height: int | None
    duration_seconds: float | None = None


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
    Hidden directories (names beginning with ``'.'``, including ``.trash/``)
    are pruned before descending so they are never entered at all.
    """
    for dirpath, dirnames, filenames in os.walk(str(root)):
        # Prune hidden dirs in-place; os.walk respects this before recursing.
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for filename in sorted(filenames):
            yield Path(dirpath) / filename


def _iter_trash_candidates(root: Path) -> Iterator[Path]:
    """Yield media files found inside ``.trash/`` subdirectories under *root*.

    Descends the tree visiting only non-hidden directories (to find ``.trash/``
    siblings at any nesting level) and then yields every file directly inside
    each ``.trash/`` directory found.  The ``.trash/`` directories themselves
    are not recursed into further, matching the flat layout written by
    :class:`CompanionActionService`.
    """
    for dirpath, dirnames, filenames in os.walk(str(root)):
        p = Path(dirpath)
        if p.name == ".trash":
            for filename in sorted(filenames):
                yield p / filename
            dirnames[:] = []  # .trash/ has no meaningful subdirs
        else:
            # Descend into non-hidden dirs and .trash/ siblings only.
            dirnames[:] = sorted(
                d for d in dirnames
                if not d.startswith(".") or d == ".trash"
            )


def _find_dcim_subtrees(root: Path) -> list[Path]:
    """Walk *root* visiting only directory entries to locate DCF subdirectories.

    A DCF subdirectory is a directory whose name matches
    :data:`DCIM_SUBDIR_PATTERN` (e.g. ``100MEDIA``, ``101GOPRO``) and whose
    immediate parent is named ``DCIM`` (case-insensitive).  This is the
    standard layout produced by digital cameras and trail cameras that follow
    the *Design rule for Camera File system* (DCF / JEITA CP-3461).

    The walk is directory-only — file entries are ignored — so it completes
    quickly even over large trees.  Hidden directories and their descendants
    are skipped.  Recursion stops when a DCF numbered directory is found
    because no further DCF nesting is expected inside those leaf directories.

    Results are cached in memory keyed by the resolved root path.  The cache
    entry is invalidated when the root directory mtime or the direct
    ``<root>/DCIM`` child mtime changes.  Call :func:`_clear_dcim_cache` to
    evict all entries (useful in tests).

    Returns a list of :class:`~pathlib.Path` objects sorted lexicographically.
    Returns an empty list when the tree contains no DCIM structure.
    """
    cache_key = str(root)
    root_mtime, dcim_mtime = _dcim_cache_mtimes(root)

    entry = _dcim_subtree_cache.get(cache_key)
    if (
        entry is not None
        and entry["root_mtime"] == root_mtime
        and entry["dcim_mtime"] == dcim_mtime
    ):
        cached_subtrees: list[str] = entry["subtrees"]  # type: ignore[assignment]
        _log.debug(
            "_find_dcim_subtrees: cache hit for %s (%d subtree(s))",
            root,
            len(cached_subtrees),
        )
        return [Path(p) for p in cached_subtrees]

    results: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(str(root)):
        p = Path(dirpath)
        if DCIM_SUBDIR_PATTERN.match(p.name) and p.parent.name.upper() == "DCIM":
            results.append(p)
            dirnames[:] = []  # leaf — no further nesting expected
            continue
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
    results_sorted = sorted(results)
    _dcim_subtree_cache[cache_key] = {
        "root_mtime": root_mtime,
        "dcim_mtime": dcim_mtime,
        "subtrees": [str(p) for p in results_sorted],
    }
    _log.debug(
        "_find_dcim_subtrees: cache miss for %s — found %d subtree(s)",
        root,
        len(results_sorted),
    )
    return results_sorted


def _iter_candidates(root: Path) -> Iterator[Path]:
    """Yield media candidate paths under *root* using a two-phase strategy.

    **Phase 1 — directory discovery**: walks *root* touching only directory
    entries (no file ``stat`` calls) to locate all DCF numbered subdirectories
    (e.g. ``DCIM/100MEDIA``).  This pass is fast because file entries are
    intentionally ignored.

    **Phase 2 — file scan**: if any DCF subtrees were found, their files are
    yielded first via :func:`_sorted_walk` so that camera media is returned as
    early as possible even when the scan root sits several levels above
    the ``DCIM/`` directory.  After exhausting every DCIM subtree, a second
    walk yields any remaining files that lie outside those subtrees.
    When no DCF subtrees are found the tree is scanned directly with
    :func:`_sorted_walk`.
    """
    _log.debug("scanning %s: phase 1 — locating DCIM subtrees", root)
    dcim_subtrees = _find_dcim_subtrees(root)

    if not dcim_subtrees:
        _log.debug("%s: no DCIM subtrees found, plain incremental walk", root)
        yield from _sorted_walk(root)
        return

    _log.debug(
        "%s: %d DCIM subtree(s) found, scanning first",
        root,
        len(dcim_subtrees),
    )
    dcim_set: frozenset[Path] = frozenset(dcim_subtrees)

    # Phase 2a — yield all files from each DCIM subtree first.
    for subtree in dcim_subtrees:
        yield from _sorted_walk(subtree)

    # Phase 2b — yield any remaining files that live outside DCIM subtrees.
    for dirpath, dirnames, filenames in os.walk(str(root)):
        p = Path(dirpath)
        # Prune hidden dirs and dirs already scanned in phase 2a so os.walk
        # never descends into them again.
        dirnames[:] = sorted(
            d for d in dirnames
            if not d.startswith(".") and (p / d) not in dcim_set
        )
        # Safety guard: skip if this dir is a DCIM subtree root or lies inside one.
        if p in dcim_set or any(s in p.parents for s in dcim_set):
            continue
        for filename in sorted(filenames):
            yield p / filename


def _probe_video_metadata(file_path: Path) -> MediaMetadata:
    """Run ``ffprobe`` on *file_path* and return duration and pixel dimensions.

    Returns a :class:`MediaMetadata` with ``width``, ``height``, and
    ``duration_seconds`` populated from the first video stream found by
    ffprobe.  Returns ``MediaMetadata(None, None, None)`` when:

    * ``ffprobe`` is not installed / not on ``$PATH``.
    * The process times out (capped at :data:`_FFPROBE_TIMEOUT` seconds).
    * The output cannot be parsed (corrupt file, audio-only, etc.).
    * Any :class:`OSError` or :class:`subprocess.SubprocessError` is raised.
    """
    if shutil.which("ffprobe") is None:
        return MediaMetadata(width=None, height=None, duration_seconds=None)

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_entries", "stream=width,height:format=duration",
        "-select_streams", "v:0",
        str(file_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_FFPROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        _log.debug("ffprobe failed for %s", file_path)
        return MediaMetadata(width=None, height=None, duration_seconds=None)

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, UnicodeDecodeError):
        _log.debug("ffprobe returned unparseable output for %s", file_path)
        return MediaMetadata(width=None, height=None, duration_seconds=None)

    streams: list[dict[str, object]] = data.get("streams", [])
    fmt: dict[str, object] = data.get("format", {})

    width: int | None = None
    height: int | None = None
    if streams:
        raw_w = streams[0].get("width")
        raw_h = streams[0].get("height")
        if isinstance(raw_w, int):
            width = raw_w
        if isinstance(raw_h, int):
            height = raw_h

    duration_seconds: float | None = None
    raw_dur = fmt.get("duration")
    if isinstance(raw_dur, str | float | int):
        try:
            duration_seconds = float(raw_dur)
        except ValueError:
            pass

    return MediaMetadata(width=width, height=height, duration_seconds=duration_seconds)


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
        self,
        root_path: Path,
        limit: int,
        offset: int = 0,
        status_filter: StatusFilter = "all",
        after_path: Path | None = None,
    ) -> Iterator[MediaItem]:
        """Yield media items one at a time as they are discovered, up to *limit*.

        Pagination is controlled by two mutually exclusive mechanisms:

        * **Cursor mode** (preferred): when *after_path* is supplied the scan
          traverses every candidate in scan order and silently skips all files
          whose resolved path compares ``<=`` *after_path*.  Once a file with
          a path ``>`` *after_path* is found, normal filtering and counting
          resume.  *offset* is ignored in cursor mode.  This mode is safe
          across concurrent reviews because it tracks *position in the
          filesystem order* rather than *position within the filtered subset* —
          so items reviewed (seen/trashed) between pages do not shift the page
          boundary.

        * **Offset mode** (legacy): when *after_path* is ``None``, *offset*
          filtered items are skipped from the start of the scan before
          yielding begins.  This mode can miss items when the filtered subset
          changes between page requests (e.g. user marks items as seen between
          page 1 and page 2), and is retained only for backward compatibility.

        *status_filter* values:

        - ``"all"``    — no filtering; return every media file.
        - ``"unseen"`` — items without a ``.seen`` companion file.
        - ``"seen"``   — items with a ``.seen`` companion file.
        - ``"locked"`` — items with a ``.lock`` companion file.
        - ``"trashed"``— items physically located inside a ``.trash/`` sibling
          directory.  These are yielded via :func:`_iter_trash_candidates`
          which explicitly descends into ``.trash/`` subdirectories that the
          normal walk skips.

        Hidden directories (names starting with ``'.'``, including ``.trash/``)
        and companion files are skipped silently and do **not** count against
        *offset* or *limit* during normal (non-trashed) scans.
        """

        normalized_root = root_path.expanduser().resolve()
        past_cursor = after_path is None  # True → start yielding immediately
        skipped = 0
        count = 0
        # Trashed items live in .trash/ subdirs, which the normal walker skips.
        if status_filter == "trashed":
            candidate_iter: Iterator[Path] = _iter_trash_candidates(normalized_root)
        else:
            candidate_iter = _iter_candidates(normalized_root)
        for candidate in candidate_iter:
            if not candidate.is_file():
                continue
            if status_filter != "trashed" and self._is_in_hidden_directory(
                candidate, normalized_root
            ):
                continue
            if self._is_companion_file(candidate):
                continue
            media_type = self._detect_media_type(candidate)
            if media_type is None:
                continue
            # Cursor mode: advance past after_path before filtering/counting.
            if not past_cursor:
                if candidate <= after_path:  # type: ignore[operator]
                    continue
                past_cursor = True
            if not self._matches_status_filter(candidate, status_filter):
                continue
            if skipped < offset:
                skipped += 1
                continue
            yield self._build_media_item(candidate, media_type)
            count += 1
            if count >= limit:
                break

    def scan_folder(self, folder_path: Path, offset: int = 0, limit: int = 100) -> ScanResult:
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

    def count_by_status(self, root_path: Path) -> dict[str, int]:
        """Count media files by status in a single pass without building MediaItem objects.

        Returns a dict with keys ``all``, ``unseen``, ``seen``, ``locked``,
        ``trashed``.  The ``all`` key includes trashed items.  The ``seen``,
        ``unseen``, and ``locked`` keys exclude trashed items (consistent with
        the behaviour of :meth:`scan_stream` status filters).
        """
        normalized_root = root_path.expanduser().resolve()
        counts: dict[str, int] = {
            "all": 0,
            "unseen": 0,
            "seen": 0,
            "locked": 0,
            "trashed": 0,
        }

        for candidate in _iter_candidates(normalized_root):
            if not candidate.is_file():
                continue
            if self._is_in_hidden_directory(candidate, normalized_root):
                continue
            if self._is_companion_file(candidate):
                continue
            if self._detect_media_type(candidate) is None:
                continue
            counts["all"] += 1
            seen_exists = candidate.with_suffix(
                f"{candidate.suffix}.seen"
            ).exists()
            locked_exists = candidate.with_suffix(
                f"{candidate.suffix}.lock"
            ).exists()
            if locked_exists:
                counts["locked"] += 1
            if seen_exists:
                counts["seen"] += 1
            else:
                counts["unseen"] += 1

        for candidate in _iter_trash_candidates(normalized_root):
            if not candidate.is_file():
                continue
            if self._is_companion_file(candidate):
                continue
            if self._detect_media_type(candidate) is None:
                continue
            counts["trashed"] += 1
            counts["all"] += 1

        return counts

    def get_folders(self, parent_path: Path) -> tuple[FolderInfo, ...]:
        """Get sorted list of immediate child folders.

        Directories that cannot be read due to permission restrictions are
        silently skipped rather than raising a 500 error to the caller.
        Errors are logged at DEBUG level so operators can diagnose permission
        issues without exposing details in API responses.
        """

        normalized_parent = parent_path.expanduser().resolve()
        if not normalized_parent.is_dir():
            _log.debug("get_folders: %s is not a directory", normalized_parent)
            return ()

        try:
            st = normalized_parent.stat()
            _log.debug(
                "get_folders: listing %s  (uid=%d gid=%d mode=%o)",
                normalized_parent,
                st.st_uid,
                st.st_gid,
                st.st_mode,
            )
            entries = sorted(normalized_parent.iterdir())
        except PermissionError as exc:
            _log.debug("get_folders: cannot list %s — %s", normalized_parent, exc)
            return ()
        except OSError as exc:
            _log.debug("get_folders: OS error listing %s — %s", normalized_parent, exc)
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
            except PermissionError as exc:
                _log.debug("get_folders: cannot check children of %s — %s", item, exc)
                has_children = False
            folders.append(
                FolderInfo(path=str(item), name=item.name, has_children=has_children)
            )

        _log.debug("get_folders: %s → %d subfolder(s) found", normalized_parent, len(folders))
        return tuple(folders)

    def _matches_status_filter(self, file_path: Path, status_filter: StatusFilter) -> bool:
        """Return True if *file_path* satisfies the requested status filter."""
        if status_filter == "all":
            return True
        is_trashed = file_path.parent.name == ".trash"
        lock_exists = file_path.with_suffix(f"{file_path.suffix}.lock").exists()
        seen_exists = file_path.with_suffix(f"{file_path.suffix}.seen").exists()
        if status_filter == "unseen":
            return not seen_exists and not is_trashed
        if status_filter == "seen":
            return seen_exists and not is_trashed
        if status_filter == "locked":
            return lock_exists
        if status_filter == "trashed":
            return is_trashed
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
                trashed=file_path.parent.name == ".trash",
                seen=file_path.with_suffix(f"{file_path.suffix}.seen").exists(),
            ),
            metadata=self._probe_metadata(file_path, media_type),
        )

    def _probe_metadata(self, file_path: Path, media_type: str) -> MediaMetadata:
        if media_type == "image":
            return self._probe_image_metadata(file_path)
        if media_type == "video":
            return _probe_video_metadata(file_path)
        return MediaMetadata(width=None, height=None)

    def _probe_image_metadata(self, file_path: Path) -> MediaMetadata:
        """Return pixel dimensions for an image file via Pillow."""
        try:
            with Image.open(file_path) as image:
                width, height = image.size
                return MediaMetadata(width=width, height=height)
        except (OSError, UnidentifiedImageError):
            return MediaMetadata(width=None, height=None)

    def _to_iso8601(self, timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
