"""Application factory and local entry point for the Media Reviewer API."""

import logging
import os
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, send_from_directory

from mediareviewer_api.api import _pregenerate_thumbnails, api_blueprint
from mediareviewer_api.config import AppSettings
from mediareviewer_api.services.companion_actions import CompanionActionService
from mediareviewer_api.services.deletion_queue import DeletionQueue
from mediareviewer_api.services.media_scanner import MediaScanner
from mediareviewer_api.services.review_config_store import ReviewConfigStore
from mediareviewer_api.services.thumbnail_cache import ThumbnailCacheService

logger = logging.getLogger(__name__)


def create_app(settings: AppSettings | None = None) -> Flask:
    """Create and configure the Flask application."""

    resolved_settings = settings or AppSettings.from_env()

    _configure_logging(
        log_level=resolved_settings.log_level,
        log_file=resolved_settings.state_directory / "mediareviewer.log",
    )
    logger.info(
        "Starting mediareviewer_api (log_level=%s, state_dir=%s)",
        resolved_settings.log_level,
        resolved_settings.state_directory,
    )

    # Optional: serve a pre-built React frontend from the same process.
    # Set MEDIAREVIEWER_STATIC_DIR to the Vite build output directory.
    static_dir_env = os.getenv("MEDIAREVIEWER_STATIC_DIR", "")
    static_dir: Path | None = Path(static_dir_env) if static_dir_env else None

    app = Flask(__name__, static_folder=None)
    app.config["MEDIAREVIEWER_SETTINGS"] = resolved_settings
    if resolved_settings.trusted_hosts:
        app.config["TRUSTED_HOSTS"] = list(resolved_settings.trusted_hosts)
    app.extensions["mediareviewer.deletion_queue"] = DeletionQueue(
        max_workers=resolved_settings.deletion_workers,
    )
    app.extensions["mediareviewer.review_config_store"] = ReviewConfigStore(
        config_file_path=resolved_settings.config_file_path,
    )
    app.extensions["mediareviewer.media_scanner"] = MediaScanner()
    app.extensions["mediareviewer.companion_actions"] = CompanionActionService()
    app.extensions["mediareviewer.thumbnail_cache"] = ThumbnailCacheService()
    app.register_blueprint(api_blueprint)

    # Warm thumbnails for all already-configured known paths so thumbnails
    # are ready even for paths that existed before this daemon started.
    if resolved_settings.auto_thumbnail_on_add:
        _start_startup_thumbnail_warmup(
            config_store=app.extensions[  # type: ignore[arg-type]
                "mediareviewer.review_config_store"
            ],
            media_scanner=app.extensions[  # type: ignore[arg-type]
                "mediareviewer.media_scanner"
            ],
            thumbnail_cache=app.extensions[  # type: ignore[arg-type]
                "mediareviewer.thumbnail_cache"
            ],
        )

    if static_dir and static_dir.is_dir():
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path: str) -> object:
            """Serve the pre-built React SPA; fall back to index.html for client-side routing."""
            target = static_dir / path
            if path and target.exists() and target.is_file():
                return send_from_directory(str(static_dir), path)
            return send_from_directory(str(static_dir), "index.html")

    return app


def _configure_logging(log_level: str, log_file: Path) -> None:
    """Configure stream and rotating-file handlers on the mediareviewer_api logger.

    Uses the ``mediareviewer_api`` package-level logger so that all sub-module
    loggers (``mediareviewer_api.api``, ``mediareviewer_api.services.*``, etc.)
    inherit the level and handlers without polluting the root logger.

    The log file is written to *log_file* (default:
    ``~/.mediareviewer/mediareviewer.log``) with rotation at 10 MB, keeping
    three backup files.  Set ``MEDIAREVIEWER_LOG_LEVEL=DEBUG`` (or
    ``server.log_level: DEBUG`` in config.yaml) to enable verbose output.
    """
    pkg_logger = logging.getLogger("mediareviewer_api")
    if pkg_logger.handlers:  # already configured — avoid duplicate handlers on re-entry
        return
    level = getattr(logging, log_level.upper(), logging.INFO)
    pkg_logger.setLevel(level)
    pkg_logger.propagate = False

    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    pkg_logger.addHandler(stream_handler)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    pkg_logger.addHandler(file_handler)


def _deduplicate_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return *paths* with any path that is a descendant of another removed.

    When a user registers both ``/mnt/card`` and
    ``/mnt/card/DCIM/100MEDIA``, the nested path would be scanned twice:
    once directly and once as a subtree discovered inside its ancestor.
    This helper removes such redundant descendants so each piece of media
    is only warmed once.

    The input order of non-redundant paths is preserved.
    """
    resolved = [p.resolve() for p in paths]
    kept: list[Path] = []
    for i, candidate in enumerate(resolved):
        if any(
            j != i and (candidate == ancestor or ancestor in candidate.parents)
            for j, ancestor in enumerate(resolved)
        ):
            logger.debug("skipping redundant warmup path %s (covered by ancestor)", candidate)
            continue
        kept.append(paths[i])
    return tuple(kept)


def _start_startup_thumbnail_warmup(
    config_store: ReviewConfigStore,
    media_scanner: MediaScanner,
    thumbnail_cache: ThumbnailCacheService,
) -> None:
    """Start one daemon thread per known path to pre-generate missing thumbnails.

    Called once at application startup so thumbnails for pre-existing paths are
    warmed even when no explicit scan has been triggered by the frontend yet.
    Already-cached and up-to-date thumbnails are skipped instantly via the
    mtime check inside ThumbnailCacheService.

    Paths that are descendants of another known path are deduplicated before
    spawning threads to avoid scanning the same files more than once.
    """
    config = config_store.load()
    for known_path in _deduplicate_paths(config.known_paths):
        t = threading.Thread(
            target=_pregenerate_thumbnails,
            args=(media_scanner, thumbnail_cache, known_path, 256),
            daemon=True,
            name=f"thumb-warm-{known_path.name}",
        )
        t.start()


def main() -> None:
    """Run the API in local development mode (Flask dev server, debug=True).

    Not used in Docker/production — the container CMD invokes gunicorn directly
    via ``gunicorn ... mediareviewer_api.app:create_app()``.
    """

    settings = AppSettings.from_env()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
