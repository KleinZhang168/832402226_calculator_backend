"""System endpoints: health check."""

import datetime

from flask import Blueprint, current_app

from src.config import Config
from src.model import history_model
from src.utils.responses import success_response

system_blueprint = Blueprint("system", __name__, url_prefix="/api")


@system_blueprint.get("/health")
def health():
    """GET /api/health - lets the front-end detect whether the API is reachable.

    The front-end calls this on start-up. When it fails the UI shows
    "backend offline" and can only accept typed input: no result is produced
    because the front-end never calculates anything itself.
    """
    try:
        total = history_model.count_all()
        database_ok = True
    except Exception:  # noqa: BLE001 - a health check must report any failure
        total = None
        database_ok = False

    payload = {
        "service": "calculator-backend",
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "error",
        "historyCount": total,
        "databasePath": current_app.config.get("DATABASE_PATH", Config.DATABASE_PATH),
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return success_response(payload, status_code=200 if database_ok else 503)
