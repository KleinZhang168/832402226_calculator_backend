"""Central configuration for the calculator backend.

Every setting can be overridden with an environment variable so that the same
code base runs unchanged on a laptop, in CI, and on a cloud platform.

Naming follows PEP 8: module level constants use UPPER_SNAKE_CASE.
"""

import os
from pathlib import Path

# Project root directory: .../832402226_calculator_backend
BASE_DIR = Path(__file__).resolve().parent.parent


def _env_str(key: str, default: str) -> str:
    """Read a string environment variable; an empty value counts as unset."""
    value = os.environ.get(key, "").strip()
    return value or default


def _env_int(key: str, default: int) -> int:
    """Read an integer environment variable, falling back on bad input."""
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_port() -> int:
    """Resolve the listening port.

    ``CALC_PORT`` wins, then the ``PORT`` variable injected by cloud platforms
    (Render, Railway, Heroku, ...), then the local default 5000. Those platforms
    expose exactly one usable port through ``PORT``; ignoring it makes the
    service unreachable.
    """
    for key in ("CALC_PORT", "PORT"):
        value = _env_int(key, 0)
        if value:
            return value
    return 5000


def _first_existing_dir(candidates):
    """Return the first candidate directory that exists.

    Used to accept both common locations of a static front-end copy:
    ``src/web`` inside this repository, or a sibling front-end project folder.
    """
    options = list(candidates)
    for path in options:
        if path.is_dir():
            return path
    return options[0]


class Config:
    """Application configuration."""

    # ---------- HTTP server ----------
    HOST = _env_str("CALC_HOST", "0.0.0.0")
    PORT = _env_port()
    # Debug mode is off by default. Turn it on locally with CALC_DEBUG=true.
    # A public deployment must never enable it: the Werkzeug debugger exposes
    # source code and allows code execution.
    DEBUG = _env_str("CALC_DEBUG", "false").lower() in ("1", "true", "yes", "on")

    # ---------- Optional static front-end hosting ----------
    # The front-end normally runs as its own process (see the front-end README).
    # When a copy of it is vendored into src/web, Flask also serves it from the
    # same origin as the API, which is what the single-service cloud deployment
    # uses. BASE_DIR already points at src/, hence "web" rather than "src/web".
    # The sibling front-end project is only a fallback for local development.
    _frontend_env = _env_str("CALC_FRONTEND_DIR", "")
    FRONTEND_DIR = (
        Path(_frontend_env)
        if _frontend_env
        else _first_existing_dir([
            BASE_DIR / "web",
            BASE_DIR.parent / "832402226_calculator_frontend" / "src",
        ])
    )

    # ---------- Database ----------
    # A single SQLite file, created automatically inside the bundled data/ dir.
    DATABASE_PATH = _env_str("CALC_DB_PATH", str(BASE_DIR / "data" / "calculator.db"))

    # ---------- Expression safety limits ----------
    # Maximum length of an expression, to keep huge inputs from tying up a worker.
    MAX_EXPRESSION_LENGTH = _env_int("CALC_MAX_EXPRESSION_LENGTH", 200)
    # Maximum number of tokens produced by the lexer.
    MAX_TOKEN_COUNT = _env_int("CALC_MAX_TOKEN_COUNT", 500)
    # Decimal precision (significant digits) used while evaluating.
    DECIMAL_PRECISION = _env_int("CALC_DECIMAL_PRECISION", 28)
    # Maximum number of decimal places shown in the formatted result.
    MAX_DISPLAY_DECIMAL_PLACES = _env_int("CALC_MAX_DISPLAY_DP", 10)
    # Absolute limit for a power exponent, so 9^9^9 cannot exhaust the CPU.
    MAX_POWER_EXPONENT = _env_int("CALC_MAX_POWER_EXPONENT", 1000)
    # Largest decimal exponent accepted before the result counts as overflow.
    MAX_DECIMAL_ADJUSTED_EXPONENT = _env_int("CALC_MAX_ADJUSTED_EXPONENT", 1000)

    # ---------- Pagination ----------
    DEFAULT_PAGE_SIZE = _env_int("CALC_DEFAULT_PAGE_SIZE", 20)
    MAX_PAGE_SIZE = _env_int("CALC_MAX_PAGE_SIZE", 100)

    # ---------- CORS ----------
    # The front-end may be opened from a browser, a phone, an emulator or a
    # mini program, so the origin is not fixed. A production deployment behind a
    # known domain should narrow this down.
    CORS_ALLOW_ORIGIN = _env_str("CALC_CORS_ORIGIN", "*")
