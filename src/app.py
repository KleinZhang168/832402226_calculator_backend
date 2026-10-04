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

    /                 the calculator page when src/web is bundled; the endpoint
                      list otherwise, so a back-end-only deployment still answers
    /api/endpoints    the endpoint list, always
    /api/...          the calculation and history endpoints
    /index.html       the static front-end entry page, when src/web/ is present
"""

import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request, send_from_directory, url_for
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import RequestRedirect

from src.config import Config
from src.controller import ALL_BLUEPRINTS
from src.middleware import cors, error_handler
from src.model import database, history_model

#: Prefix shared by every business endpoint.
API_PREFIX = "/api"

#: Path of the endpoint list. The root path serves the calculator itself when a
#: static front-end is bundled, so the list lives here instead.
ENDPOINTS_PATH = API_PREFIX + "/endpoints"


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

    # The static hosting decides what the root path serves, so it is wired up
    # first; _register_index_route uses the entry page it reports back.
    entry_name = _register_frontend_routes(app)
    _register_index_route(app, entry_name)

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


def endpoint_list() -> dict:
    """The self-describing payload that names every API endpoint.

    Served at ``/api/endpoints``, and also at ``/`` when no static front-end is
    bundled: a back-end-only deployment should still answer something useful in a
    browser instead of a bare 404.
    """
    return {
        "success": True,
        "service": "832402226 calculator backend",
        "version": "1.0.0",
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "endpoints": [
            "GET    /                     the calculator page (or this list, when no page is bundled)",
            "GET    " + ENDPOINTS_PATH + "       this list",
            "GET    /api/health",
            "POST   /api/calculate           {\"expression\": \"(1+2)*3\"}",
            "POST   /api/calculate/preview   {\"expression\": \"(1+2)*3\"} (evaluate only)",
            "GET    /api/history?page=1&pageSize=20",
            "GET    /api/history/count",
            "DELETE /api/history/{id}",
            "DELETE /api/history",
        ],
    }


def _register_index_route(app: Flask, entry_name: Optional[str] = None) -> None:
    """Register the root route and the endpoint list.

    The root path serves the calculator itself whenever a static front-end is
    bundled, because ``https://<host>/`` is the URL people are given: showing them
    a JSON endpoint list there made a working deployment look broken. The
    endpoint list stays available at ``/api/endpoints`` for anyone who wants it,
    and the root falls back to it in a back-end-only deployment.
    """

    @app.get("/api/endpoints")
    def endpoint_list_route():
        """Always the endpoint list, whatever the root path does."""
        return jsonify(endpoint_list())

    @app.get("/")
    def index():
        """The calculator when it is bundled, otherwise the endpoint list."""
        if entry_name:
            return send_from_directory(app.config["FRONTEND_DIR"], entry_name)
        return jsonify(endpoint_list())

    # Convenient during development: how many records are stored right now.
    @app.get("/api/history/count")
    def history_count():
        return jsonify({"success": True, "total": history_model.count_all()})


def _api_method_adapter(app: Flask):
    """A URL adapter that resolves API endpoints only.

    ``MapAdapter.match`` is the supported way to ask "which methods does this path
    allow?". The application's own map cannot answer that, because the static
    catch-all ``/<path:filename>`` covers every path and would answer for it. A
    copy of the map without the catch-all exposes exactly the declared API
    endpoints, so a method mismatch surfaces as ``MethodNotAllowed`` instead of
    being absorbed by the static route.

    Each rule is copied with ``Rule.empty()``: a rule instance belongs to a single
    ``Map``, and binding one that is already bound raises
    ``RuntimeError: url rule ... already bound to map``. The adapter is cached in
    the application config so the copy is built once, not on every request.

    ``Rule.match`` and ``Rule._compiled_pattern`` are not used: neither exists in
    Werkzeug 3.x, and reaching for a private attribute would break silently.
    """
    from werkzeug.routing import Map

    cache_key = "_calculator_api_adapter"
    adapter = app.config.get(cache_key)
    if adapter is None:
        api_map = Map([rule.empty() for rule in app.url_map.iter_rules()
                       if rule.rule.startswith(API_PREFIX)])
        adapter = api_map.bind("localhost")
        app.config[cache_key] = adapter
    return adapter


def _resolve_api_error(app: Flask):
    """Return the error for an API path the static route caught, or ``None``.

    ``/<path:filename>`` swallows the request whenever its weight ties with an API
    rule. Measured with the catch-all registered::

        GET  /api/calculate  -> frontend_asset(filename="api/calculate")
        POST /api/calculate  -> calculate.calculate

    Asking the API-only adapter which methods the path allows settles it: a method
    the endpoints do not declare raises 405 with that list, which keeps a wrong
    method distinguishable from a path that does not exist. ``None`` means no API
    endpoint claims the path, and the caller lets the missing asset produce the
    usual JSON 404.
    """
    from werkzeug.exceptions import MethodNotAllowed as WerkzeugMethodNotAllowed

    try:
        _api_method_adapter(app).match(request.path)
    except WerkzeugMethodNotAllowed as error:
        # valid_methods holds the methods the rule allows; the one that was tried
        # is part of the set the rule responds to, so both are reported.
        allowed = set(error.valid_methods or ())
        allowed.add(request.method)
        return MethodNotAllowed(
            valid_methods=sorted(m for m in allowed if m not in ("HEAD", "OPTIONS"))
        )
    except NotFound:
        return None

    # An endpoint accepts this exact request, so the static route wrongly won.
    # Falling through to the missing asset still yields the JSON 404 for the path.
    return None


def _register_frontend_routes(app: Flask) -> None:
    """Serve a static front-end copy from the same origin, when one is present.

    The two projects are designed to run as separate processes. This optional
    hosting mode keeps a browser from issuing cross origin requests, which is
    useful on a host that exposes a single port. When no front-end copy exists
    (for example when running the unit tests), the routes are skipped silently.

    :return: the entry file name that will be served, or ``None`` when static
        hosting is off. The caller uses it to decide what the root path returns.
    """
    frontend_dir = app.config.get("FRONTEND_DIR")

    if frontend_dir is None:
        app.logger.info("No static front-end configured, skipping static hosting")
        return None

    # Accept either conventional entry file name.
    entry_name = None
    for candidate in ("index.html", "calculator.html"):
        if (frontend_dir / candidate).is_file():
            entry_name = candidate
            break

    if entry_name is None:
        # Logged at warning level with the resolved paths, because this is the
        # difference between a working page and a service that only answers JSON.
        # A relative CALC_FRONTEND_DIR used to resolve against the working
        # directory, which on Render sits one level above the checkout root, so
        # the directory tested here did not exist and every page 404ed.
        app.logger.warning(
            "Static front-end hosting DISABLED: no index.html or calculator.html in %s "
            "(cwd=%s, repository root=%s). Every page request will receive the JSON 404 "
            "handler; check CALC_FRONTEND_DIR and the vendored src/web copy.",
            frontend_dir, Path.cwd(), Path(app.root_path).resolve().parent,
        )
        return None

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

        Two guards keep this catch-all route from shadowing the API:

        * a path under the API prefix never refers to a static file, so it is
          resolved through the URL map again. A method mismatch then still
          produces the correct 405 instead of a misleading 404, and an unknown
          endpoint produces the usual JSON 404;
        * a non-existent file naturally falls through to the JSON 404 handler
          rather than an HTML error page, and ``send_from_directory`` rejects
          path traversal such as ``../``.

        The API prefix is compared without its leading slash: the ``path``
        converter strips it, so the value here is "api/calculate" and never
        "/api/calculate". Comparing against ``API_PREFIX`` itself therefore never
        matched, which silently turned this guard into dead code and let every
        such request be treated as a missing static file.
        """
        normalized = filename.lstrip("/")
        api_prefix_bare = API_PREFIX.lstrip("/")
        if normalized == api_prefix_bare or normalized.startswith(api_prefix_bare + "/"):
            api_error = _resolve_api_error(app)
            if api_error is not None:
                raise api_error

        return send_from_directory(frontend_dir, filename)

    return entry_name
