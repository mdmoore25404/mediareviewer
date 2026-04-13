"""Tests for folder browsing and pagination endpoints."""

from pathlib import Path

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def test_get_folders_returns_child_folders(tmp_path: Path) -> None:
    """GET /api/folders should return immediate child folders."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    # Create nested folder structure
    (review_directory / "folder1").mkdir()
    (review_directory / "folder2").mkdir()
    (review_directory / "folder3").mkdir()
    (review_directory / ".hidden").mkdir()  # Should be ignored

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    # Add review path
    client.post("/api/review-paths", json={"path": str(review_directory)})

    response = client.get(f"/api/folders?path={review_directory}")

    assert response.status_code == 200
    payload = response.get_json()
    assert "path" in payload
    assert "folders" in payload
    assert len(payload["folders"]) == 3
    folder_names = {f["name"] for f in payload["folders"]}
    assert folder_names == {"folder1", "folder2", "folder3"}


def test_get_folders_respects_hidden_paths(tmp_path: Path) -> None:
    """GET /api/folders should respect hidden picker paths."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    hidden_directory = tmp_path / "hidden"
    review_directory.mkdir(parents=True)
    hidden_directory.mkdir(parents=True)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(hidden_directory,),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.get(f"/api/folders?path={hidden_directory}")

    assert response.status_code == 403
    payload = response.get_json()
    assert "error" in payload


def test_get_folders_returns_empty_for_no_subdirs(tmp_path: Path) -> None:
    """GET /api/folders should return empty list when no subdirectories exist."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    response = client.get(f"/api/folders?path={review_directory}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["folders"] == []


def test_get_folder_files_returns_paginated_media(tmp_path: Path) -> None:
    """GET /api/folders/{path}/files should return paginated media items."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    # Create test image files
    test_image_path = review_directory / "test1.jpg"
    test_image_path.write_text("fake image data")
    test_image_path2 = review_directory / "test2.png"
    test_image_path2.write_text("fake image data")

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    # Add review path
    client.post("/api/review-paths", json={"path": str(review_directory)})

    response = client.get(
        f"/api/folders/files?path={review_directory}&offset=0&limit=100"
    )
    

    assert response.status_code == 200
    payload = response.get_json()
    assert "path" in payload
    assert "offset" in payload
    assert "limit" in payload
    assert "count" in payload
    assert "items" in payload
    assert payload["offset"] == 0
    assert payload["limit"] == 100


def test_get_folder_files_respects_offset_limit(tmp_path: Path) -> None:
    """GET /api/folders/{path}/files should respect offset and limit parameters."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    # Create 5 test files
    for i in range(5):
        (review_directory / f"file{i}.jpg").write_text("fake image")

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    # Add review path
    client.post("/api/review-paths", json={"path": str(review_directory)})

    # Get first 2 items
    response1 = client.get(
        f"/api/folders/files?path={review_directory}&offset=0&limit=2"
    )
    payload1 = response1.get_json()
    assert len(payload1["items"]) == 2

    # Get next 2 items
    response2 = client.get(
        f"/api/folders/files?path={review_directory}&offset=2&limit=2"
    )
    assert response2.status_code == 200
    payload2 = response2.get_json()
    assert len(payload2["items"]) == 2

def test_get_folder_files_validates_parameters(tmp_path: Path) -> None:
    """GET /api/folders/{path}/files should validate offset and limit."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    review_directory.mkdir(parents=True)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    # Add review path
    client.post("/api/review-paths", json={"path": str(review_directory)})

    # Invalid offset (negative)
    response = client.get("/api/folders/files?offset=-1&limit=100")
    assert response.status_code == 400

    # Invalid limit (zero)
    response = client.get("/api/folders/files?offset=0&limit=0")
    assert response.status_code == 400

    # Invalid limit (too large)
    response = client.get("/api/folders/files?offset=0&limit=2000")
    assert response.status_code == 400


def test_get_folder_files_respects_known_paths(tmp_path: Path) -> None:
    """GET /api/folders/{path}/files should reject folders outside known paths."""

    state_directory = tmp_path / "state"
    review_directory = tmp_path / "review"
    other_directory = tmp_path / "other"
    review_directory.mkdir(parents=True)
    other_directory.mkdir(parents=True)

    settings = AppSettings(
        state_directory=state_directory,
        hidden_picker_paths=(),
        deletion_workers=1,
    )
    app = create_app(settings)
    client: FlaskClient = app.test_client()

    # Add only review_directory as known path
    client.post("/api/review-paths", json={"path": str(review_directory)})

    # Try to access other_directory
    response = client.get(f"/api/folders/files?path={other_directory}&offset=0&limit=100")
    assert response.status_code == 403
