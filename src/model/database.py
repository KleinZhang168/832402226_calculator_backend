"""SQLite connection management and schema creation.

Design notes:
    * One connection per HTTP request, stored on Flask's ``g`` and closed by the
      ``teardown_appcontext`` hook, so no connection is ever shared between
      threads;
    * ``row_factory`` is set to ``sqlite3.Row`` so rows can be read by column
      name;
    * the schema statements all use ``IF NOT EXISTS``, therefore
      :func:`init_database` can run on every start without touching existing
      data.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from flask import Flask, current_app, g

from src.config import Config

#: Key under which the connection is stored in the Flask application context.
_DB_KEY = "calculator_db"

#: Table and index statements; safe to execute repeatedly.
SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS calculation_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        expression  TEXT    NOT NULL,
        result      REAL    NOT NULL,
        result_text TEXT    NOT NULL,
        created_at  TEXT    NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_calculation_history_created_at
        ON calculation_history (created_at DESC, id DESC)
    """,
)


def _connect(database_path: str) -> sqlite3.Connection:
    """Open a SQLite connection."""
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_connection() -> sqlite3.Connection:
    """Return the connection of the current request, creating it on demand.

    The path is read from ``current_app.config["DATABASE_PATH"]`` so tests can
    point the application at a temporary database through a custom config class.
    """
    if _DB_KEY not in g:
        database_path = current_app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
        setattr(g, _DB_KEY, _connect(database_path))
    return getattr(g, _DB_KEY)


def close_connection(exception: Optional[BaseException] = None) -> None:
    """Close the request connection. Registered as ``app.teardown_appcontext``."""
    connection = g.pop(_DB_KEY, None)
    if connection is not None:
        connection.close()


def init_database(database_path: Optional[str] = None) -> str:
    """Create the data directory, the table and the index.

    :return: the database file path that was used
    """
    path = database_path or Config.DATABASE_PATH
    connection = _connect(path)
    try:
        with connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
    finally:
        connection.close()
    return path


def init_app(app: Flask) -> None:
    """Register the connection life cycle hook on the Flask application."""
    app.teardown_appcontext(close_connection)
