"""Tests for MediaScanner DCIM detection and incremental walk helpers."""

import os
import time
from pathlib import Path

from mediareviewer_api.services.media_scanner import (
    MediaScanner,
    _clear_dcim_cache,
    _find_dcim_subtrees,
    _iter_candidates,
    _iter_trash_candidates,
    _sorted_walk,
    is_dcim_path,
)

# ---------------------------------------------------------------------------
# is_dcim_path — detection cases
# ---------------------------------------------------------------------------


def _make_dcim_root(base: Path) -> Path:
    """Return a ``DCIM/`` directory populated with two numbered subdirs."""
    dcim = base / "DCIM"
    (dcim / "100MEDIA").mkdir(parents=True)
    (dcim / "101MEDIA").mkdir(parents=True)
    return dcim


def test_is_dcim_path_case1_dcim_root(tmp_path: Path) -> None:
    """Path named DCIM containing numbered subdirs is detected."""
    dcim = _make_dcim_root(tmp_path)
    assert is_dcim_path(dcim) is True


def test_is_dcim_path_case2_numbered_subdir(tmp_path: Path) -> None:
    """A numbered subdir (e.g. 100MEDIA) inside a DCIM parent is detected."""
    dcim = _make_dcim_root(tmp_path)
    assert is_dcim_path(dcim / "100MEDIA") is True


def test_is_dcim_path_case3_parent_contains_dcim(tmp_path: Path) -> None:
    """A plain directory whose immediate child is a DCIM root is detected."""
    _make_dcim_root(tmp_path)
    assert is_dcim_path(tmp_path) is True


def test_is_dcim_path_rejects_plain_directory(tmp_path: Path) -> None:
    """An ordinary directory with no DCIM structure is not detected."""
    (tmp_path / "photos" / "2026").mkdir(parents=True)
    assert is_dcim_path(tmp_path) is False


def test_is_dcim_path_rejects_dcim_dir_without_numbered_subdirs(tmp_path: Path) -> None:
    """A directory named DCIM but without numbered children is not detected."""
    dcim = tmp_path / "DCIM"
    (dcim / "backup").mkdir(parents=True)
    assert is_dcim_path(dcim) is False


def test_is_dcim_path_case1_is_case_insensitive(tmp_path: Path) -> None:
    """DCIM directory name matching is case-insensitive (dcim == DCIM)."""
    dcim = tmp_path / "dcim"
    (dcim / "100MEDIA").mkdir(parents=True)
    assert is_dcim_path(dcim) is True


# ---------------------------------------------------------------------------
# _sorted_walk — incremental traversal
# ---------------------------------------------------------------------------


def _build_tree(base: Path) -> list[Path]:
    """Create a small two-level tree and return the expected sorted file paths."""
    (base / "DCIM" / "100MEDIA").mkdir(parents=True)
    (base / "DCIM" / "101MEDIA").mkdir(parents=True)
    files = [
        base / "DCIM" / "100MEDIA" / "IMG_0002.JPG",
        base / "DCIM" / "100MEDIA" / "IMG_0001.JPG",
        base / "DCIM" / "101MEDIA" / "IMG_0003.JPG",
    ]
    for f in files:
        f.write_bytes(b"x")
    return sorted(files)


def test_sorted_walk_yields_files_in_lexicographic_order(tmp_path: Path) -> None:
    """_sorted_walk must yield files in the same order as sorted(rglob('*'))."""
    expected = _build_tree(tmp_path)
    result = list(_sorted_walk(tmp_path))
    assert result == expected


def test_sorted_walk_skips_hidden_directories(tmp_path: Path) -> None:
    """_sorted_walk must not yield files inside hidden directories."""
    (tmp_path / "visible").mkdir()
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "visible" / "a.jpg").write_bytes(b"x")
    (tmp_path / ".hidden" / "b.jpg").write_bytes(b"x")

    result = list(_sorted_walk(tmp_path))
    names = [p.name for p in result]
    assert "a.jpg" in names
    assert "b.jpg" not in names


def test_sorted_walk_yields_files_only(tmp_path: Path) -> None:
    """_sorted_walk must not yield directories — only files."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "file.jpg").write_bytes(b"x")

    result = list(_sorted_walk(tmp_path))
    assert all(p.is_file() for p in result)


# ---------------------------------------------------------------------------
# _find_dcim_subtrees — directory discovery
# ---------------------------------------------------------------------------


def test_find_dcim_subtrees_returns_dcf_numbered_dirs(tmp_path: Path) -> None:
    """_find_dcim_subtrees returns DCF numbered subdirs sorted lexicographically."""
    (tmp_path / "DCIM" / "102MEDIA").mkdir(parents=True)
    (tmp_path / "DCIM" / "100MEDIA").mkdir(parents=True)

    result = _find_dcim_subtrees(tmp_path)
    assert [p.name for p in result] == ["100MEDIA", "102MEDIA"]


def test_find_dcim_subtrees_returns_empty_for_non_dcim(tmp_path: Path) -> None:
    """_find_dcim_subtrees returns an empty list when no DCIM structure exists."""
    (tmp_path / "photos" / "2026").mkdir(parents=True)

    assert _find_dcim_subtrees(tmp_path) == []


def test_find_dcim_subtrees_deeply_nested(tmp_path: Path) -> None:
    """_find_dcim_subtrees reaches DCIM subtrees buried under arbitrary intermediate dirs."""
    nested = tmp_path / "Storage" / "CAM" / "DCIM" / "100MEDIA"
    nested.mkdir(parents=True)

    result = _find_dcim_subtrees(tmp_path)
    assert len(result) == 1
    assert result[0].name == "100MEDIA"


def test_find_dcim_subtrees_skips_hidden_directories(tmp_path: Path) -> None:
    """_find_dcim_subtrees must not descend into hidden directories."""
    (tmp_path / ".Spotlight-V100" / "DCIM" / "100MEDIA").mkdir(parents=True)
    (tmp_path / "visible" / "DCIM" / "100MEDIA").mkdir(parents=True)

    result = _find_dcim_subtrees(tmp_path)
    assert len(result) == 1
    assert result[0] == tmp_path / "visible" / "DCIM" / "100MEDIA"


# ---------------------------------------------------------------------------
# _find_dcim_subtrees — in-memory cache
# ---------------------------------------------------------------------------


def test_find_dcim_subtrees_cache_hit_returns_same_result(tmp_path: Path) -> None:
    """A second call for the same root path returns a cache hit with identical results."""
    _clear_dcim_cache()
    (tmp_path / "DCIM" / "100MEDIA").mkdir(parents=True)

    first = _find_dcim_subtrees(tmp_path)
    second = _find_dcim_subtrees(tmp_path)
    assert first == second


def test_find_dcim_subtrees_cache_invalidates_on_root_mtime_change(
    tmp_path: Path,
) -> None:
    """Adding a new top-level dir changes root mtime and forces a cache miss."""
    _clear_dcim_cache()
    (tmp_path / "DCIM" / "100MEDIA").mkdir(parents=True)

    first = _find_dcim_subtrees(tmp_path)
    assert len(first) == 1

    # Add a second camera directory at the root level then explicitly bump
    # root mtime — tmpfs can have 1-second granularity so we cannot rely on
    # the natural mtime change being visible within the same test second.
    (tmp_path / "cam2" / "DCIM" / "100MEDIA").mkdir(parents=True)
    future = time.time() + 2.0
    os.utime(str(tmp_path), (future, future))

    second = _find_dcim_subtrees(tmp_path)
    assert len(second) == 2


def test_find_dcim_subtrees_cache_invalidates_on_dcim_mtime_change(
    tmp_path: Path,
) -> None:
    """Adding a new numbered subdir changes DCIM mtime and forces a cache miss."""
    _clear_dcim_cache()
    (tmp_path / "DCIM" / "100MEDIA").mkdir(parents=True)

    first = _find_dcim_subtrees(tmp_path)
    assert len(first) == 1

    # Create a new numbered subdir then explicitly bump DCIM/ mtime — tmpfs
    # can have 1-second granularity so we cannot rely on the natural mtime
    # change being visible within the same test second.
    (tmp_path / "DCIM" / "101MEDIA").mkdir(parents=True)
    future = time.time() + 2.0
    os.utime(str(tmp_path / "DCIM"), (future, future))

    second = _find_dcim_subtrees(tmp_path)
    assert len(second) == 2


def test_find_dcim_subtrees_clear_cache_forces_fresh_walk(tmp_path: Path) -> None:
    """_clear_dcim_cache evicts all entries so the next call does a fresh walk."""
    _clear_dcim_cache()
    (tmp_path / "DCIM" / "100MEDIA").mkdir(parents=True)

    _find_dcim_subtrees(tmp_path)  # populate cache
    _clear_dcim_cache()
    (tmp_path / "DCIM" / "101MEDIA").mkdir(
        parents=True
    )  # would be missed on a stale hit

    result = _find_dcim_subtrees(tmp_path)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# _iter_candidates — two-phase DCIM-first scan
# ---------------------------------------------------------------------------


def test_iter_candidates_yields_files_in_order_for_dcim(tmp_path: Path) -> None:
    """_iter_candidates returns files in lexicographic order for DCIM roots."""
    expected = _build_tree(tmp_path / "card")
    result = [p for p in _iter_candidates(tmp_path / "card") if p.is_file()]
    assert result == expected


def test_iter_candidates_yields_files_in_order_for_non_dcim(tmp_path: Path) -> None:
    """_iter_candidates returns files in lexicographic order for non-DCIM directories."""
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "b.jpg").write_bytes(b"x")
    (tmp_path / "photos" / "a.jpg").write_bytes(b"x")

    result = [p for p in _iter_candidates(tmp_path) if p.is_file()]
    assert [p.name for p in result] == ["a.jpg", "b.jpg"]


def test_iter_candidates_works_for_deeply_nested_dcim(tmp_path: Path) -> None:
    """_iter_candidates handles roots several levels above DCIM (real-world SD card layout)."""
    # Mirrors: /mnt/trailcam/NNNNdriveway/Generic MassStorage/GARDEPRO/DCIM/100MEDIA/
    nested = (
        tmp_path / "trailcam-root" / "Generic MassStorage" / "GARDEPRO" / "DCIM" / "100MEDIA"
    )
    nested.mkdir(parents=True)
    (nested / "IMG_001.JPG").write_bytes(b"x")
    (nested / "IMG_002.JPG").write_bytes(b"x")

    result = [p for p in _iter_candidates(tmp_path / "trailcam-root") if p.is_file()]
    assert [p.name for p in result] == ["IMG_001.JPG", "IMG_002.JPG"]


def test_iter_candidates_yields_dcim_files_before_non_dcim_files(tmp_path: Path) -> None:
    """_iter_candidates yields DCIM subtree files before files outside the DCIM tree."""
    # Non-DCIM file alphabetically before the DCIM container dir name.
    (tmp_path / "a_readme.txt").write_bytes(b"x")
    dcim_dir = tmp_path / "storage" / "DCIM" / "100MEDIA"
    dcim_dir.mkdir(parents=True)
    (dcim_dir / "IMG_001.JPG").write_bytes(b"x")

    result = [p for p in _iter_candidates(tmp_path) if p.is_file()]
    names = [p.name for p in result]
    assert names.index("IMG_001.JPG") < names.index("a_readme.txt")


def test_iter_candidates_non_dcim_files_not_duplicated(tmp_path: Path) -> None:
    """Files outside DCIM subtrees must appear exactly once in the output."""
    (tmp_path / "notes.txt").write_bytes(b"x")
    dcim_dir = tmp_path / "DCIM" / "100MEDIA"
    dcim_dir.mkdir(parents=True)
    (dcim_dir / "IMG_001.JPG").write_bytes(b"x")

    result = [p for p in _iter_candidates(tmp_path) if p.is_file()]
    names = [p.name for p in result]
    assert names.count("notes.txt") == 1
    assert names.count("IMG_001.JPG") == 1


# ---------------------------------------------------------------------------
# _iter_trash_candidates — .trash/ directory walk
# ---------------------------------------------------------------------------


def test_iter_trash_candidates_yields_files_in_trash_dirs(tmp_path: Path) -> None:
    """_iter_trash_candidates must yield files inside .trash/ subdirectories."""
    trash_dir = tmp_path / ".trash"
    trash_dir.mkdir()
    (trash_dir / "IMG_001.JPG").write_bytes(b"x")
    (trash_dir / "IMG_002.JPG").write_bytes(b"x")
    (tmp_path / "keep.jpg").write_bytes(b"x")

    result = list(_iter_trash_candidates(tmp_path))
    names = [p.name for p in result]
    assert "IMG_001.JPG" in names
    assert "IMG_002.JPG" in names
    assert "keep.jpg" not in names


def test_iter_trash_candidates_skips_non_trash_dirs(tmp_path: Path) -> None:
    """_iter_trash_candidates must not yield files from non-.trash directories."""
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "visible.jpg").write_bytes(b"x")
    trash_dir = tmp_path / ".trash"
    trash_dir.mkdir()
    (trash_dir / "hidden.jpg").write_bytes(b"x")

    result = list(_iter_trash_candidates(tmp_path))
    names = [p.name for p in result]
    assert names == ["hidden.jpg"]


def test_iter_trash_candidates_handles_nested_trash_dirs(tmp_path: Path) -> None:
    """_iter_trash_candidates yields files from .trash/ at multiple nesting levels."""
    sub = tmp_path / "DCIM" / "100MEDIA"
    sub.mkdir(parents=True)
    (sub / "IMG_001.JPG").write_bytes(b"x")
    top_trash = tmp_path / ".trash"
    top_trash.mkdir()
    (top_trash / "old.jpg").write_bytes(b"x")
    sub_trash = sub / ".trash"
    sub_trash.mkdir()
    (sub_trash / "sub.jpg").write_bytes(b"x")

    result = list(_iter_trash_candidates(tmp_path))
    names = sorted(p.name for p in result)
    assert names == ["old.jpg", "sub.jpg"]
    # Normal files must not appear.
    assert "IMG_001.JPG" not in names


def test_iter_trash_candidates_yields_sorted_order(tmp_path: Path) -> None:
    """Files inside a single .trash/ directory are yielded in lexicographic order."""
    trash_dir = tmp_path / ".trash"
    trash_dir.mkdir()
    for name in ["z.jpg", "a.jpg", "m.jpg"]:
        (trash_dir / name).write_bytes(b"x")

    result = [p.name for p in _iter_trash_candidates(tmp_path)]
    assert result == ["a.jpg", "m.jpg", "z.jpg"]


# ---------------------------------------------------------------------------
# MediaScanner — trashed status filter
# ---------------------------------------------------------------------------


def test_scan_stream_trashed_filter_returns_items_in_trash_dir(tmp_path: Path) -> None:
    """scan_stream with status_filter='trashed' yields files inside .trash/ dirs."""
    trash_dir = tmp_path / ".trash"
    trash_dir.mkdir()
    (trash_dir / "trashed.jpg").write_bytes(b"x")
    (tmp_path / "normal.jpg").write_bytes(b"x")

    scanner = MediaScanner()
    items = list(scanner.scan_stream(tmp_path, limit=100, status_filter="trashed"))
    names = [i.name for i in items]
    assert names == ["trashed.jpg"]
    assert all(i.status.trashed for i in items)


def test_scan_stream_trashed_items_excluded_from_all_filter(tmp_path: Path) -> None:
    """scan_stream with status_filter='all' must NOT yield files from .trash/ dirs."""
    trash_dir = tmp_path / ".trash"
    trash_dir.mkdir()
    (trash_dir / "trashed.jpg").write_bytes(b"x")
    (tmp_path / "normal.jpg").write_bytes(b"x")

    scanner = MediaScanner()
    items = list(scanner.scan_stream(tmp_path, limit=100, status_filter="all"))
    names = [i.name for i in items]
    assert "trashed.jpg" not in names
    assert "normal.jpg" in names


def test_scan_stream_trashed_items_excluded_from_unseen_filter(tmp_path: Path) -> None:
    """scan_stream with status_filter='unseen' must not yield files from .trash/ dirs."""
    trash_dir = tmp_path / ".trash"
    trash_dir.mkdir()
    (trash_dir / "trashed.jpg").write_bytes(b"x")

    scanner = MediaScanner()
    items = list(scanner.scan_stream(tmp_path, limit=100, status_filter="unseen"))
    names = [i.name for i in items]
    assert "trashed.jpg" not in names


# ---------------------------------------------------------------------------
# MediaScanner — cursor-based pagination (after_path)
# ---------------------------------------------------------------------------


def test_scan_stream_cursor_resumes_after_given_path(tmp_path: Path) -> None:
    """scan_stream with after_path must yield only files that come after it in scan order."""
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.jpg").write_bytes(b"x")
    (tmp_path / "c.jpg").write_bytes(b"x")

    scanner = MediaScanner()
    # Simulate page 1: scan to get cursor path.
    page1 = list(scanner.scan_stream(tmp_path, limit=2))
    assert [i.name for i in page1] == ["a.jpg", "b.jpg"]

    cursor = (tmp_path / "b.jpg").resolve()
    page2 = list(scanner.scan_stream(tmp_path, limit=2, after_path=cursor))
    assert [i.name for i in page2] == ["c.jpg"]


def test_scan_stream_cursor_no_gap_when_earlier_items_filtered(tmp_path: Path) -> None:
    """Cursor must not skip items even when previously loaded items no longer match filter.

    This is the regression test for the offset-shift gap bug.
    """
    for name in ("f01.jpg", "f02.jpg", "f03.jpg", "f04.jpg"):
        (tmp_path / name).write_bytes(b"x")

    scanner = MediaScanner()
    # Page 1: first 2 unseen items.
    page1 = list(scanner.scan_stream(tmp_path, limit=2, status_filter="unseen"))
    assert [i.name for i in page1] == ["f01.jpg", "f02.jpg"]
    cursor = (tmp_path / "f02.jpg").resolve()

    # Mark page-1 items as seen — simulates user reviewing them.
    (tmp_path / "f01.jpg.seen").write_text("", encoding="utf-8")
    (tmp_path / "f02.jpg.seen").write_text("", encoding="utf-8")

    # Page 2 with cursor: f03, f04 must be returned; NOT skipped.
    page2 = list(
        scanner.scan_stream(tmp_path, limit=2, status_filter="unseen", after_path=cursor)
    )
    assert [i.name for i in page2] == ["f03.jpg", "f04.jpg"]


def test_scan_stream_cursor_returns_empty_when_at_end(tmp_path: Path) -> None:
    """scan_stream with a cursor pointing to the last file returns no items."""
    (tmp_path / "only.jpg").write_bytes(b"x")
    cursor = (tmp_path / "only.jpg").resolve()

    scanner = MediaScanner()
    result = list(scanner.scan_stream(tmp_path, limit=10, after_path=cursor))
    assert result == []

