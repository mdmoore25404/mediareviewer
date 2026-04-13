"""Application factory and local entry point for the Media Reviewer API."""

from flask import Flask

from mediareviewer_api.api import api_blueprint
from mediareviewer_api.config import AppSettings
from mediareviewer_api.services.deletion_queue import DeletionQueue


def create_app(settings: AppSettings | None = None) -> Flask:
    """Create and configure the Flask application."""

    resolved_settings = settings or AppSettings.from_env()
    app = Flask(__name__)
    app.config["MEDIAREVIEWER_SETTINGS"] = resolved_settings
    app.extensions["mediareviewer.deletion_queue"] = DeletionQueue(
        max_workers=resolved_settings.deletion_workers,
    )
    app.register_blueprint(api_blueprint)
    return app


def main() -> None:
    """Run the API in local development mode."""

    settings = AppSettings.from_env()
    app = create_app(settings)
    app.run(host=settings.host, port=settings.port, debug=True)


if __name__ == "__main__":
    main()
