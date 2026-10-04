"""History endpoints."""

from flask import Blueprint, request

from src.service.history import HistoryService
from src.utils.responses import success_response

history_blueprint = Blueprint("history", __name__, url_prefix="/api")


# strict_slashes=False accepts both /api/history and /api/history/, so a stray
# trailing slash does not turn into a 308 redirect (some in-app web views do not
# follow 308 responses reliably).
@history_blueprint.get("/history", strict_slashes=False)
def list_history():
    """GET /api/history?page=1&pageSize=20

    Success response (HTTP 200)::

        {"success": true, "total": 2, "page": 1, "pageSize": 20,
         "list": [{"id": 2, "expression": "5*8", "result": 40,
                   "resultText": "40", "createdAt": "2026-10-01 10:21:00"}]}
    """
    result = HistoryService.list_history(
        page=request.args.get("page"),
        page_size=request.args.get("pageSize"),
    )
    return success_response(result)


@history_blueprint.delete("/history/<record_id>", strict_slashes=False)
def delete_history(record_id: str):
    """DELETE /api/history/{id}

    Success response (HTTP 200)::

        {"success": true, "message": "Record deleted", "id": 3, "deleted": 1}

    Returns HTTP 404 when no record has that id.
    """
    result = HistoryService.delete_history(record_id)
    return success_response(result, message="Record deleted")


@history_blueprint.delete("/history", strict_slashes=False)
def clear_history():
    """DELETE /api/history - remove every history record (optional feature).

    Success response (HTTP 200)::

        {"success": true, "message": "History cleared", "deleted": 12}
    """
    result = HistoryService.clear_history()
    return success_response(result, message="History cleared")
