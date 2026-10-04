"""CORS middleware.

The front-end can be opened from a browser, a phone, an emulator or a mini
program developer tool, so the origin is not fixed and cross origin requests are
allowed by default. A production deployment behind a known domain should set
``CALC_CORS_ORIGIN`` to that domain.
"""

from flask import Flask, current_app

from src.config import Config


def init_app(app: Flask) -> None:
    """Add the CORS headers to every response."""

    @app.after_request
    def add_cors_headers(response):
        # Read from current_app.config so that create_app(CustomConfig) works.
        allow_origin = current_app.config.get(
            "CORS_ALLOW_ORIGIN", Config.CORS_ALLOW_ORIGIN
        )
        response.headers["Access-Control-Allow-Origin"] = allow_origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response
