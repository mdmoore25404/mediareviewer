"""Tests for MediaScanner DCIM detection and incremental walk helpers."""

from pathlib import Path

from mediareviewer_api.services.media_scanner import (
    _find_dcim_subtrees,
    _iter_candidates,
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

