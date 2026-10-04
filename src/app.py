"""Flask application factory.

Layered architecture (front-end -> HTTP/JSON -> controller -> service -> model
-> database)::

    src/
    ├── app.py                 application factory: blueprints, middleware, database
    ├── calculator.py          public entry point of the calculation core
    ├── config.py              central configuration, overridable by environment
    ├── controller/            controller layer: parse requests, wrap responses
    ├── service/               service layer: parsing, evaluation, history rules
    ├── model/                 model layer: SQLite connection and table CRUD
    ├── middleware/            CORS and centralised error handling
    └── utils/                 business exceptions and unified response bodies

URL layout::

    /                 endpoint list (JSON, handy to confirm the service is up)
    /api/...          the calculation and history endpoints
    /index.html       optional static front-end when src/web/ is present
"""

import datetime

from flask import Flask, jsonify, send_from_directory

from src.config import Config
from src.controller import ALL_BLUEPRINTS
from src.middleware import cors, error_handler
from src.model import database, history_model

#: Prefix shared by every business endpoint.
API_PREFIX = "/api"


def create_app(config_object=Config) -> Flask:
    """Create and configure the Flask application."""
    # static_folder=None disables Flask's built-in /static/<filename> route.
    # The back end ships no static assets of its own, and that route would match
    # before the optional front-end routes registered below.
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object)

    # Emit Chinese (and any other non-ASCII) characters literally instead of
    # \uXXXX escapes, which keeps the JSON readable during debugging.
    _disable_ascii_escape(app)

    # Model layer: connection life cycle + schema creation.
    database.init_app(app)

    # Middleware: centralised errors and CORS.
    error_handler.init_app(app)
    cors.init_app(app)

    # Controller layer: register every blueprint.
    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    _register_index_route(app)
    _register_frontend_routes(app)

    # Create the schema on first start; existing data is never touched.
    database.init_database(app.config["DATABASE_PATH"])
    app.logger.info("SQLite database ready: %s", app.config["DATABASE_PATH"])

    return app


def _disable_ascii_escape(app: Flask) -> None:
    """Turn off ASCII escaping of JSON (compatible with Flask before and after 2.2)."""
    try:
        app.json.ensure_ascii = False
    except AttributeError:  # pragma: no cover - Flask < 2.2
        app.config["JSON_AS_ASCII"] = False


def _register_index_route(app: Flask) -> None:
    """Root route: return the endpoint list so the API can be checked in a browser."""

    @app.get("/")
    def index():
        return jsonify({
            "success": True,
            "service": "832402226 calculator backend",
            "version": "1.0.0",
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "endpoints": [
                "GET    /api/health",
                "POST   /api/calculate           {\"expression\": \"(1+2)*3\"}",
                "POST   /api/calculate/preview   {\"expression\": \"(1+2)*3\"} (evaluate only)",
                "GET    /api/history?page=1&pageSize=20",
                "GET    /api/history/count",
                "DELETE /api/history/{id}",
                "DELETE /api/history",
            ],
        })

    # Convenient during development: how many records are stored right now.
    @app.get("/api/history/count")
    def history_count():
        return jsonify({"success": True, "total": history_model.count_all()})


def _register_frontend_routes(app: Flask) -> None:
    """Serve a static front-end copy from the same origin, when one is present.

    The two projects are designed to run as separate processes. This optional
    hosting mode keeps a browser from issuing cross origin requests, which is
    useful on a host that exposes a single port. When no front-end copy exists
    (for example when running the unit tests), the routes are skipped silently.
    """
    frontend_dir = app.config.get("FRONTEND_DIR")

    if frontend_dir is None:
        app.logger.info("No static front-end configured, skipping static hosting")
        return

    # Accept either conventional entry file name.
    entry_name = None
    for candidate in ("index.html", "calculator.html"):
        if (frontend_dir / candidate).is_file():
            entry_name = candidate
            break

    if entry_name is None:
        app.logger.info("No front-end entry page found, skipping static hosting: %s",
                        frontend_dir)
        return

    app.logger.info("Static front-end hosting enabled: %s (entry %s)",
                    frontend_dir, entry_name)

    @app.get("/index.html")
    def frontend_index():
        """Front-end entry page."""
        return send_from_directory(frontend_dir, entry_name)

    @app.get("/app")
    def frontend_index_alias():
        """A shorter alias for the entry page."""
        return send_from_directory(frontend_dir, entry_name)

    @app.get("/<path:filename>")
    def frontend_asset(filename: str):
        """Static assets: css, js, images.

        ``send_from_directory`` rejects path traversal such as ``../``, and
        unmatched paths fall through to the JSON 404 handler instead of an HTML
        error page.
        """
        return send_from_directory(frontend_dir, filename)
