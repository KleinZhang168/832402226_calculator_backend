"""Centralised error handling.

Every failure leaves the API as the same JSON shape, so the front-end only has
to look at ``success``:

    * :class:`ApiError` and its subclasses -> the status code and error code
      carried by the exception;
    * HTTP errors such as 404 / 405 -> converted into the same structure instead
      of Flask's HTML error page;
    * anything unexpected -> logged and reported as HTTP 500 without leaking a
      stack trace.
"""

from flask import Flask, request
from werkzeug.exceptions import HTTPException

from src.utils.exceptions import ApiError
from src.utils.responses import error_response


def init_app(app: Flask) -> None:
    """Register the error handlers on the Flask application."""

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        """Business errors: 400 / 404 / 500 as declared by the exception."""
        return error_response(error.message, error.code, error.status_code)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """HTTP errors raised by Flask or Werkzeug."""
        status_code = error.code or 500
        code_map = {
            400: "BAD_REQUEST",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            415: "UNSUPPORTED_MEDIA_TYPE",
        }
        code = code_map.get(status_code, "HTTP_ERROR")
        if status_code == 404:
            message = "No such endpoint: %s %s" % (request.method, request.path)
        elif status_code == 405:
            message = "Method %s is not allowed on this endpoint" % request.method
        else:
            message = error.description or "The request could not be processed"
        return error_response(message, code, status_code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Catch-all for unexpected failures."""
        app.logger.exception("Internal server error: %s", error)
        return error_response("Internal server error, please try again later",
                              "INTERNAL_ERROR", 500)
