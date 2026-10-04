"""Unified response bodies.

The contract matches the format required by the assignment:

    success::

        {
          "success": true,
          "expression": "1+2",
          "result": 3
        }

    failure::

        {
          "success": false,
          "message": "Invalid expression"
        }

Extra fields (``code``, ``id``, ``resultText``, ...) are additive extensions of
that contract: clients that only read ``success`` / ``message`` / ``result``
keep working.
"""

from typing import Optional

from flask import jsonify


def success_response(data: Optional[dict] = None,
                     status_code: int = 200,
                     message: Optional[str] = None):
    """Build a success response.

    :param data:        business fields, merged into the top level of the body
    :param status_code: HTTP status code, 200 by default
    :param message:     optional human readable note
    """
    body: dict = {"success": True}
    if message is not None:
        body["message"] = message
    if data:
        body.update(data)
    return jsonify(body), status_code


def error_response(message: str, code: str = "BAD_REQUEST", status_code: int = 400):
    """Build an error response."""
    return jsonify({
        "success": False,
        "code": code,
        "message": message,
    }), status_code
