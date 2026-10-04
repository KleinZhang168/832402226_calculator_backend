"""Data access object for the ``calculation_history`` table.

This module only talks to the database; business rules live in the service
layer, which keeps each layer focused on a single responsibility.

Table layout:

    calculation_history
    -------------------
    id          INTEGER  auto increment primary key
    expression  TEXT     the expression submitted by the client (normalised)
    result      REAL     numeric result, convenient for further computation
    result_text TEXT     result as a string, so large or high precision values
                         survive JSON serialisation
    created_at  TEXT     local time, formatted as YYYY-MM-DD HH:MM:SS
"""

import sqlite3
from typing import List, Optional

from src.model.database import get_connection
from src.utils.exceptions import DatabaseError

#: Column order shared by every query, so all endpoints return the same shape.
_COLUMNS = "id, expression, result, result_text, created_at"


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a ``sqlite3.Row`` into the dictionary returned by the API."""
    return {
        "id": row["id"],
        "expression": row["expression"],
        "result": row["result"],
        "resultText": row["result_text"],
        "createdAt": row["created_at"],
    }


def insert(expression: str, result: float, result_text: str, created_at: str) -> dict:
    """Insert one history record and return the stored row."""
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO calculation_history (expression, result, result_text, created_at) "
                "VALUES (?, ?, ?, ?)",
                (expression, result, result_text, created_at),
            )
        record_id = cursor.lastrowid
    except sqlite3.Error as exc:  # pragma: no cover - needs a real database failure
        raise DatabaseError("Failed to write the calculation history: %s" % exc) from exc

    record = find_by_id(record_id)
    if record is None:  # pragma: no cover - cannot normally happen
        raise DatabaseError("The inserted history record could not be read back")
    return record


def find_by_id(record_id: int) -> Optional[dict]:
    """Look up a single record by primary key, or return ``None``."""
    connection = get_connection()
    row = connection.execute(
        "SELECT %s FROM calculation_history WHERE id = ?" % _COLUMNS,
        (record_id,),
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def find_all(limit: int, offset: int) -> List[dict]:
    """Return one page of records, newest first."""
    connection = get_connection()
    rows = connection.execute(
        "SELECT %s FROM calculation_history ORDER BY id DESC LIMIT ? OFFSET ?" % _COLUMNS,
        (limit, offset),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def count_all() -> int:
    """Return the total number of stored records."""
    connection = get_connection()
    row = connection.execute("SELECT COUNT(*) AS total FROM calculation_history").fetchone()
    return int(row["total"])


def delete_by_id(record_id: int) -> int:
    """Delete one record, returning the number of affected rows (0 if absent)."""
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute(
                "DELETE FROM calculation_history WHERE id = ?", (record_id,)
            )
        return cursor.rowcount
    except sqlite3.Error as exc:  # pragma: no cover
        raise DatabaseError("Failed to delete the history record: %s" % exc) from exc


def delete_all() -> int:
    """Delete every record, returning the number of affected rows."""
    connection = get_connection()
    try:
        with connection:
            cursor = connection.execute("DELETE FROM calculation_history")
        return cursor.rowcount
    except sqlite3.Error as exc:  # pragma: no cover
        raise DatabaseError("Failed to clear the calculation history: %s" % exc) from exc
