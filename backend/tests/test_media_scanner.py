"""Tests for MediaScanner DCIM detection and incremental walk helpers."""

from pathlib import Path

from mediareviewer_api.services.media_scanner import _iter_candidates, _sorted_walk, is_dcim_path

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
# _iter_candidates — routing logic
# ---------------------------------------------------------------------------


def test_iter_candidates_uses_incremental_walk_for_dcim(tmp_path: Path) -> None:
    """_iter_candidates returns items from the incremental walk for DCIM roots."""
    expected = _build_tree(tmp_path / "card")
    result = [p for p in _iter_candidates(tmp_path / "card") if p.is_file()]
    assert result == expected


def test_iter_candidates_falls_back_for_non_dcim(tmp_path: Path) -> None:
    """_iter_candidates falls back to sorted rglob for non-DCIM directories."""
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "b.jpg").write_bytes(b"x")
    (tmp_path / "photos" / "a.jpg").write_bytes(b"x")

    result = [p for p in _iter_candidates(tmp_path) if p.is_file()]
    assert [p.name for p in result] == ["a.jpg", "b.jpg"]
