"""Calculation endpoints."""

from flask import Blueprint, request

from src.service.calculator import CalculatorService
from src.utils.exceptions import ValidationError
from src.utils.responses import success_response

calculate_blueprint = Blueprint("calculate", __name__, url_prefix="/api")


def _read_expression():
    """Read the ``expression`` field from the request.

    JSON is the primary format: ``{"expression": "(1+2)*3"}``. Form encoded and
    plain text bodies are also accepted so the endpoint can be exercised with
    curl without quoting JSON.
    """
    body = request.get_json(silent=True)
    if isinstance(body, dict):
        return body.get("expression")
    if body is not None:
        raise ValidationError('The request body must be a JSON object, e.g. {"expression": "1+2"}')

    if request.form:
        return request.form.get("expression")

    raw = request.get_data(as_text=True) or ""
    raw = raw.strip()
    if raw and not raw.startswith("{"):
        return raw

    raise ValidationError('The request body must be a JSON object, e.g. {"expression": "1+2"}')


@calculate_blueprint.post("/calculate")
def calculate():
    """POST /api/calculate

    Request body::

        {"expression": "(1+2)*3"}

    Success response (HTTP 200)::

        {"success": true, "id": 1, "expression": "(1+2)*3",
         "result": 9, "resultText": "9", "createdAt": "2026-10-01 10:20:00"}

    The record is stored in the calculation history.
    """
    record = CalculatorService.calculate(_read_expression())
    return success_response({
        "id": record["id"],
        "expression": record["expression"],
        "result": record["result"],
        "resultText": record["resultText"],
        "createdAt": record["createdAt"],
    })


@calculate_blueprint.post("/calculate/preview")
def preview():
    """POST /api/calculate/preview

    Evaluates the expression without storing it, which the UI uses for the live
    preview while the user is typing. The evaluation still happens on the
    server, so the front-end never computes a result by itself.
    """
    return success_response(CalculatorService.preview(_read_expression()))
