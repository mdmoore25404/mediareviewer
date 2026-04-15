"""Tests for the GET /api/logs endpoint."""

from pathlib import Path

from flask.testing import FlaskClient

from mediareviewer_api.app import create_app
from mediareviewer_api.config import AppSettings


def _make_client(tmp_path: Path) -> FlaskClient:
    """Return a test client whose state directory is *tmp_path*."""

    settings = AppSettings(state_directory=tmp_path)
    app = create_app(settings)
    return app.test_client()


def test_logs_returns_empty_when_log_file_missing(tmp_path: Path) -> None:
    """GET /api/logs should report available=false when no log file exists yet."""

    client = _make_client(tmp_path)
    response = client.get("/api/logs")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["available"] is False
    assert payload["lines"] == []
    assert payload["logFile"].endswith("mediareviewer.log")


def test_logs_returns_all_lines_when_file_has_few_lines(tmp_path: Path) -> None:
    """GET /api/logs should return every line when the file is shorter than the limit."""

    log_file = tmp_path / "mediareviewer.log"
    log_file.write_text("line one\nline two\nline three\n", encoding="utf-8")

    client = _make_client(tmp_path)
    response = client.get("/api/logs")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["available"] is True
    assert payload["lines"] == ["line one", "line two", "line three"]


def test_logs_tails_to_requested_line_count(tmp_path: Path) -> None:
    """GET /api/logs?lines=N should return only the last N lines."""

    log_file = tmp_path / "mediareviewer.log"
    all_lines = [f"line {i}" for i in range(50)]
    log_file.write_text("\n".join(all_lines) + "\n", encoding="utf-8")

    client = _make_client(tmp_path)
    response = client.get("/api/logs?lines=10")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["available"] is True
    assert payload["lines"] == [f"line {i}" for i in range(40, 50)]


def test_logs_clamps_lines_to_maximum(tmp_path: Path) -> None:
    """Requesting more than 2000 lines should be silently clamped to 2000."""

    log_file = tmp_path / "mediareviewer.log"
    log_file.write_text("\n".join(f"x{i}" for i in range(100)) + "\n", encoding="utf-8")

    client = _make_client(tmp_path)
    # ?lines=99999 should be clamped — we only care that it does not error out
    response = client.get("/api/logs?lines=99999")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["available"] is True
    assert len(payload["lines"]) == 100  # file has 100 lines, all returned


def test_logs_returns_400_for_non_integer_lines_param(tmp_path: Path) -> None:
    """GET /api/logs?lines=abc should return HTTP 400."""

    client = _make_client(tmp_path)
    response = client.get("/api/logs?lines=abc")

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
