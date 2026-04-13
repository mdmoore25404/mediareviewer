"""HTTP routes exposed by the Media Reviewer API."""

from dataclasses import asdict
from typing import cast

from flask import Blueprint, Response, current_app, jsonify

from mediareviewer_api.config import AppSettings
from mediareviewer_api.services.deletion_queue import DeletionQueue, DeletionQueueSnapshot

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
