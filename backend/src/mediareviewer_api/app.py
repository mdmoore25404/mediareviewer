"""Application factory and local entry point for the Media Reviewer API."""

import os
from pathlib import Path

from flask import Flask, send_from_directory

from mediareviewer_api.api import api_blueprint
from mediareviewer_api.config import AppSettings
from mediareviewer_api.services.companion_actions import CompanionActionService
from mediareviewer_api.services.deletion_queue import DeletionQueue
from mediareviewer_api.services.media_scanner import MediaScanner
from mediareviewer_api.services.review_config_store import ReviewConfigStore
from mediareviewer_api.services.thumbnail_cache import ThumbnailCacheService


def create_app(settings: AppSettings | None = None) -> Flask:
    """Create and configure the Flask application."""

    resolved_settings = settings or AppSettings.from_env()

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


def main() -> None:
    """Run the API in local development mode."""

    settings = AppSettings.from_env()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
