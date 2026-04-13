"""Application factory and local entry point for the Media Reviewer API."""

from flask import Flask

from mediareviewer_api.api import api_blueprint
from mediareviewer_api.config import AppSettings
from mediareviewer_api.services.companion_actions import CompanionActionService
from mediareviewer_api.services.deletion_queue import DeletionQueue
from mediareviewer_api.services.media_scanner import MediaScanner
from mediareviewer_api.services.review_config_store import ReviewConfigStore


def create_app(settings: AppSettings | None = None) -> Flask:
    """Create and configure the Flask application."""

    resolved_settings = settings or AppSettings.from_env()
    app = Flask(__name__)
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
    app.register_blueprint(api_blueprint)
    return app


def main() -> None:
    """Run the API in local development mode."""

    settings = AppSettings.from_env()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=True)


if __name__ == "__main__":
    main()
