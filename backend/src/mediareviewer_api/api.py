"""HTTP routes exposed by the Media Reviewer API."""

import json
import os
import threading
from dataclasses import asdict
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

from flask import Blueprint, Response, current_app, jsonify, request, send_file, stream_with_context

from mediareviewer_api.config import AppSettings
from mediareviewer_api.services.companion_actions import (
    CompanionActionService,
    CompanionStatus,
    LockedItemError,
)
from mediareviewer_api.services.deletion_queue import DeletionQueue, DeletionQueueSnapshot
from mediareviewer_api.services.media_scanner import MediaScanner, StatusFilter
from mediareviewer_api.services.review_config_store import ReviewConfigStore
from mediareviewer_api.services.thumbnail_cache import ThumbnailCacheService

api_blueprint = Blueprint("api", __name__, url_prefix="/api")


@api_blueprint.get("/health")
def get_health() -> Response:
    """Return a typed snapshot of application status for the frontend shell."""

    settings = cast(AppSettings, current_app.config["MEDIAREVIEWER_SETTINGS"])
    deletion_queue = cast(
        DeletionQueue,
        current_app.extensions["mediareviewer.deletion_queue"],
    )
    queue_snapshot = cast(DeletionQueueSnapshot, deletion_queue.snapshot())
    payload = {
        "status": "ok",
        "service": "mediareviewer-api",
        "settings": {
            "stateDirectory": str(settings.state_directory),
            "hiddenPickerPaths": [str(path) for path in settings.hidden_picker_paths],
            "deletionWorkers": settings.deletion_workers,
        },
        "deletionQueue": asdict(queue_snapshot),
    }
    return jsonify(payload)


@api_blueprint.get("/folders")
def get_folders() -> Response:
    """Get immediate child folders under a parent path."""

    settings = cast(AppSettings, current_app.config["MEDIAREVIEWER_SETTINGS"])
    media_scanner = cast(
        MediaScanner,
        current_app.extensions["mediareviewer.media_scanner"],
    )

    raw_path = request.args.get("path", type=str)
    if not raw_path:
        return jsonify({"error": "Query parameter 'path' is required."}), 400

    parent_path = Path(raw_path).expanduser().resolve()
    if not parent_path.exists() or not parent_path.is_dir():
        return jsonify({"error": "Path must be an existing directory."}), 400

    if _is_hidden_path(parent_path, settings.hidden_picker_paths):
        return jsonify({"error": "Path is hidden by picker policy."}), 403

    folders = media_scanner.get_folders(parent_path)
    folders_payload: list[dict[str, object]] = []
    for folder_info in folders:
        folders_payload.append(asdict(folder_info))

    payload = {
        "path": str(parent_path),
        "folders": folders_payload,
    }
    return jsonify(payload)


@api_blueprint.get("/folders/<path:folder_path>/files")
@api_blueprint.get("/folders/files")
def get_folder_files() -> Response:
    """Get paginated media files in a folder (non-recursive)."""

    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )
    media_scanner = cast(
        MediaScanner,
        current_app.extensions["mediareviewer.media_scanner"],
    )
    thumbnail_cache = cast(
        ThumbnailCacheService,
        current_app.extensions["mediareviewer.thumbnail_cache"],
    )

    offset = request.args.get("offset", default=0, type=int)
    limit = request.args.get("limit", default=100, type=int)

    if offset < 0:
        return jsonify({"error": "Query parameter 'offset' must be >= 0."}), 400
    if limit <= 0 or limit > 1000:
        return jsonify({"error": "Query parameter 'limit' must be between 1 and 1000."}), 400

    raw_path = request.args.get("path", type=str)
    if not raw_path:
        return jsonify({"error": "Query parameter 'path' is required."}), 400

    target_folder = Path(raw_path).expanduser().resolve()
    config = config_store.load()
    if not _is_under_known_path(target_folder, config.known_paths):
        return jsonify({"error": "Folder is not under a configured review path."}), 403

    scan_result = media_scanner.scan_folder(folder_path=target_folder, offset=offset, limit=limit)
    items_payload: list[dict[str, object]] = []
    for item in scan_result.items:
        review_path = next(
            (
                path
                for path in config.known_paths
                if Path(item.path) == path or str(item.path).startswith(str(path / ""))
            ),
            None,
        )
        if review_path:
            thumbnail_cache.ensure_thumbnail(Path(item.path), review_path, size=256)
        item_payload = item.to_payload()
        item_payload["thumbnailUrl"] = _build_media_thumbnail_url(item.path, 256)
        items_payload.append(item_payload)

    payload = {
        "path": str(target_folder),
        "offset": offset,
        "limit": limit,
        "count": len(scan_result.items),
        "ignoredCount": scan_result.ignored_count,
        "items": items_payload,
    }
    return jsonify(payload)


@api_blueprint.get("/review-paths")
def get_review_paths() -> Response:
    """Return configured review paths and hidden picker paths."""

    settings = cast(AppSettings, current_app.config["MEDIAREVIEWER_SETTINGS"])
    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )
    config = config_store.load()
    payload = {
        "knownPaths": [str(path) for path in config.known_paths],
        "hiddenPickerPaths": [str(path) for path in settings.hidden_picker_paths],
    }
    return jsonify(payload)


@api_blueprint.post("/review-paths")
def add_review_path() -> Response:
    """Add and persist a new review path if it is valid and not hidden."""

    settings = cast(AppSettings, current_app.config["MEDIAREVIEWER_SETTINGS"])
    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )

    request_body = request.get_json(silent=True)
    if not isinstance(request_body, dict):
        return jsonify({"error": "Expected JSON object body."}), 400

    raw_path = request_body.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return jsonify({"error": "Field 'path' must be a non-empty string."}), 400

    review_path = Path(raw_path).expanduser().resolve()
    if not review_path.exists() or not review_path.is_dir():
        return jsonify({"error": "Path must exist and be a readable directory."}), 400

    if _is_hidden_path(review_path, settings.hidden_picker_paths):
        return jsonify({"error": "Path is hidden by picker policy."}), 403

    updated = config_store.add_known_path(review_path)
    payload = {
        "addedPath": str(review_path),
        "knownPaths": [str(path) for path in updated.known_paths],
    }
    return jsonify(payload), 201


@api_blueprint.get("/media-items/stream")
def stream_media_items() -> Response:
    """Stream media items as NDJSON, yielding each item as soon as it is found.

    Each line of the response body is a JSON object.  Item lines have the same
    shape as a single element from the ``items`` array that the old polling
    endpoint returned.  The final line has the shape
    ``{"type": "done", "count": N}`` to let the client confirm how many items
    were actually streamed.
    """

    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )
    media_scanner = cast(
        MediaScanner,
        current_app.extensions["mediareviewer.media_scanner"],
    )
    thumbnail_cache = cast(
        ThumbnailCacheService,
        current_app.extensions["mediareviewer.thumbnail_cache"],
    )

    raw_path = request.args.get("path", type=str)
    if not raw_path:
        return jsonify({"error": "Query parameter 'path' is required."}), 400

    limit = request.args.get("limit", default=50, type=int)
    if limit <= 0 or limit > 10000:
        return jsonify({"error": "Query parameter 'limit' must be between 1 and 10000."}), 400

    offset = request.args.get("offset", default=0, type=int)
    if offset < 0:
        return jsonify({"error": "Query parameter 'offset' must be >= 0."}), 400

    raw_status_filter = request.args.get("statusFilter", default="all", type=str)
    valid_status_filters = {"all", "unseen", "seen", "locked", "trashed"}
    if raw_status_filter not in valid_status_filters:
        msg = (
            "Query parameter 'statusFilter' must be one of:"
            " all, unseen, seen, locked, trashed."
        )
        return jsonify({"error": msg}), 400
    status_filter: StatusFilter = raw_status_filter  # type: ignore[assignment]

    requested_path = Path(raw_path).expanduser().resolve()
    config = config_store.load()
    if requested_path not in config.known_paths:
        return jsonify({"error": "Path is not configured as a known review path."}), 403

    @stream_with_context
    def generate() -> Response:
        count = 0
        for item in media_scanner.scan_stream(
            root_path=requested_path,
            limit=limit,
            offset=offset,
            status_filter=status_filter,
        ):
            item_payload = item.to_payload()
            item_payload["thumbnailUrl"] = _build_media_thumbnail_url(item.path, 256)
            yield json.dumps(item_payload) + "\n"
            count += 1
        yield json.dumps({"type": "done", "count": count}) + "\n"

    # Start a low-priority daemon thread that warms the thumbnail cache for
    # every item in the path (not just the current page) so future scrolls
    # and filter changes find thumbnails ready on disk.
    pregenerate_thread = threading.Thread(
        target=_pregenerate_thumbnails,
        args=(media_scanner, thumbnail_cache, requested_path, 256),
        daemon=True,
        name=f"thumb-warm-{requested_path.name}",
    )
    pregenerate_thread.start()

    return Response(generate(), content_type="application/x-ndjson")


@api_blueprint.get("/media-file")
def get_media_file() -> Response:
    """Serve an image or video file under a configured review path."""

    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )

    raw_path = request.args.get("path", type=str)
    if not raw_path:
        return jsonify({"error": "Query parameter 'path' is required."}), 400

    media_path = Path(raw_path).expanduser().resolve()
    if not media_path.exists() or not media_path.is_file():
        return jsonify({"error": "Path must be an existing media file."}), 400

    config = config_store.load()
    if not _is_under_known_path(media_path, config.known_paths):
        return jsonify({"error": "Path is not under a configured review path."}), 403

    return send_file(media_path, conditional=True)


@api_blueprint.get("/media-thumbnail")
def get_media_thumbnail() -> Response:
    """Serve a cached thumbnail from disk, generating it if needed."""

    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )
    thumbnail_cache = cast(
        ThumbnailCacheService,
        current_app.extensions["mediareviewer.thumbnail_cache"],
    )

    raw_path = request.args.get("path", type=str)
    if not raw_path:
        return jsonify({"error": "Query parameter 'path' is required."}), 400

    size = request.args.get("size", default=256, type=int)
    if size <= 0 or size > 1024:
        return jsonify({"error": "Query parameter 'size' must be between 1 and 1024."}), 400

    media_path = Path(raw_path).expanduser().resolve()
    if not media_path.exists() or not media_path.is_file():
        return jsonify({"error": "Path must be an existing media file."}), 400

    config = config_store.load()
    if not _is_under_known_path(media_path, config.known_paths):
        return jsonify({"error": "Path is not under a configured review path."}), 403

    review_path = next(
        (
            path
            for path in config.known_paths
            if media_path == path or str(media_path).startswith(str(path / ""))
        ),
        None,
    )
    if not review_path:
        return jsonify({"error": "Could not determine review path for media file."}), 400

    thumbnail = thumbnail_cache.ensure_thumbnail(media_path, review_path, size=size)
    return send_file(thumbnail.file_path, mimetype="image/png", conditional=True)


@api_blueprint.post("/media-actions")
def post_media_action() -> Response:
    """Apply a companion-file action to a media item under a known review path."""

    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )
    action_service = cast(
        CompanionActionService,
        current_app.extensions["mediareviewer.companion_actions"],
    )
    thumbnail_cache = cast(
        ThumbnailCacheService,
        current_app.extensions["mediareviewer.thumbnail_cache"],
    )

    request_body = request.get_json(silent=True)
    if not isinstance(request_body, dict):
        return jsonify({"error": "Expected JSON object body."}), 400

    raw_path = request_body.get("path")
    action = request_body.get("action")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return jsonify({"error": "Field 'path' must be a non-empty string."}), 400
    if action not in {"lock", "unlock", "trash", "untrash", "seen", "unseen"}:
        msg = (
            "Field 'action' must be one of"
            " lock, unlock, trash, untrash, seen, unseen."
        )
        return jsonify({"error": msg}), 400

    media_path = Path(raw_path).expanduser().resolve()
    if not media_path.exists() or not media_path.is_file():
        return jsonify({"error": "Path must be an existing media file."}), 400

    config = config_store.load()
    if not _is_under_known_path(media_path, config.known_paths):
        return jsonify({"error": "Path is not under a configured review path."}), 403

    try:
        status = cast(CompanionStatus, action_service.apply(media_path=media_path, action=action))
    except LockedItemError as exc:
        return jsonify({"error": str(exc)}), 409

    if action == "trash":
        review_path = next(
            (
                path
                for path in config.known_paths
                if media_path == path or str(media_path).startswith(str(path / ""))
            ),
            None,
        )
        if review_path:
            thumbnail_cache.delete_thumbnail(media_path, review_path)

    payload = {
        "path": str(media_path),
        "action": action,
        "status": {
            "locked": status.locked,
            "trashed": status.trashed,
            "seen": status.seen,
        },
    }
    return jsonify(payload)


@api_blueprint.post("/empty-trash")
def post_empty_trash() -> Response:
    """Permanently delete all media files (and their companions) marked as trashed.

    Iterates over every configured known review path, finds files with a ``.trash``
    companion, removes the media file and all its companion files, and purges the
    cached thumbnail.  Locked items are skipped even if they are also trashed.

    Returns a ``deleted`` count and a list of paths that could not be removed.
    """

    config_store = cast(
        ReviewConfigStore,
        current_app.extensions["mediareviewer.review_config_store"],
    )
    thumbnail_cache = cast(
        ThumbnailCacheService,
        current_app.extensions["mediareviewer.thumbnail_cache"],
    )

    config = config_store.load()
    deleted: list[str] = []
    errors: list[str] = []

    for review_path in config.known_paths:
        if not review_path.is_dir():
            continue
        for candidate in sorted(review_path.rglob("*")):
            if not candidate.is_file():
                continue
            trash_marker = candidate.with_suffix(f"{candidate.suffix}.trash")
            if not trash_marker.exists():
                continue
            lock_marker = candidate.with_suffix(f"{candidate.suffix}.lock")
            if lock_marker.exists():
                # Locked items are never deleted automatically
                continue
            # Remove the media file, all companion files, and the thumbnail
            try:
                for companion_suffix in (".lock", ".trash", ".seen"):
                    companion = candidate.with_suffix(f"{candidate.suffix}{companion_suffix}")
                    if companion.exists():
                        companion.unlink()
                thumbnail_cache.delete_thumbnail(candidate, review_path)
                candidate.unlink()
                deleted.append(str(candidate))
            except OSError as exc:
                errors.append(f"{candidate}: {exc.strerror}")
        # Remove orphaned thumbnails whose source files were deleted outside
        # of this application (e.g. manual SD card management).
        thumbnail_cache.prune_orphaned_thumbnails(review_path)

    return jsonify({"deleted": len(deleted), "paths": deleted, "errors": errors})


def _build_media_thumbnail_url(media_path: str, size: int) -> str:
    """Build a relative thumbnail route for a media item payload."""

    return f"/api/media-thumbnail?{urlencode({'path': media_path, 'size': size})}"


def _pregenerate_thumbnails(
    media_scanner: object,
    thumbnail_cache_svc: object,
    review_path: Path,
    size: int,
) -> None:
    """Generate thumbnails for every media item in *review_path*.

    Intended to run in a daemon background thread so that thumbnails are ready
    before the user scrolls to them.  Already-cached and up-to-date thumbnails
    are skipped quickly via the mtime check.  The thread runs at a lower
    process-level CPU priority when ``os.nice`` is available.
    """
    try:
        os.nice(10)
    except (OSError, AttributeError):
        pass
    from mediareviewer_api.services.media_scanner import MediaScanner
    from mediareviewer_api.services.thumbnail_cache import ThumbnailCacheService

    scanner = cast(MediaScanner, media_scanner)
    cache = cast(ThumbnailCacheService, thumbnail_cache_svc)
    try:
        for item in scanner.scan_stream(
            root_path=review_path,
            limit=100_000,
            offset=0,
            status_filter="all",
        ):
            cache.ensure_thumbnail(Path(item.path), review_path, size=size)
    except Exception:  # noqa: BLE001 — background thread must not crash silently
        pass


def _is_hidden_path(candidate: Path, hidden_paths: tuple[Path, ...]) -> bool:
    """Return true when candidate falls under a hidden path prefix."""

    for hidden_path in hidden_paths:
        try:
            candidate.relative_to(hidden_path)
            return True
        except ValueError:
            continue
    return False


def _is_under_known_path(candidate: Path, known_paths: tuple[Path, ...]) -> bool:
    """Return true when candidate is inside at least one configured known path."""

    for known_path in known_paths:
        try:
            candidate.relative_to(known_path)
            return True
        except ValueError:
            continue
    return False
