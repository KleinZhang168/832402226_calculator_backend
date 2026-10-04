"""Database initialisation script.

Usage::

    python scripts/init_db.py            # create the table (skipped if it exists)
    python scripts/init_db.py --reset    # delete the old file first (clears history)
    python scripts/init_db.py --demo     # create the table and insert 3 sample rows

The script is idempotent: running it again never fails and never destroys data
unless ``--reset`` is passed.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Allow `python scripts/init_db.py` from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config                     # noqa: E402
from src.model.database import init_database      # noqa: E402
from src.model.database import SCHEMA_STATEMENTS  # noqa: E402

#: Sample rows, handy when demonstrating the history page.
DEMO_RECORDS = (
    ("1+2", 3.0, "3", "2026-10-01 10:20:00"),
    ("5*8", 40.0, "40", "2026-10-01 10:21:00"),
    ("(2+3)*4", 20.0, "20", "2026-10-01 10:22:00"),
)


def reset_database(path: str) -> None:
    """Delete the existing database file."""
    file_path = Path(path)
    if file_path.exists():
        file_path.unlink()
        print("[reset] removed the existing database file: %s" % file_path)
    else:
        print("[reset] no database file to remove: %s" % file_path)


def insert_demo_records(path: str) -> int:
    """Insert the sample rows and return how many were written."""
    connection = sqlite3.connect(path)
    try:
        with connection:
            cursor = connection.executemany(
                "INSERT INTO calculation_history "
                "(expression, result, result_text, created_at) VALUES (?, ?, ?, ?)",
                DEMO_RECORDS,
            )
        return cursor.rowcount
    finally:
        connection.close()


def describe_schema(path: str) -> None:
    """Print the table layout, which is useful in the written report."""
    connection = sqlite3.connect(path)
    try:
        print("\n[schema] calculation_history")
        print("  %-12s %-8s %-6s %s" % ("column", "type", "pk", "description"))
        print("  " + "-" * 60)
        descriptions = {
            "id": "auto increment primary key",
            "expression": "the expression submitted by the client",
            "result": "numeric result",
            "result_text": "result formatted for display",
            "created_at": "calculation time YYYY-MM-DD HH:MM:SS",
        }
        for row in connection.execute("PRAGMA table_info(calculation_history)"):
            print("  %-12s %-8s %-6s %s" % (
                row[1], row[2], "yes" if row[5] else "no",
                descriptions.get(row[1], ""),
            ))
        total = connection.execute(
            "SELECT COUNT(*) FROM calculation_history"
        ).fetchone()[0]
        print("\n[stats] records currently stored: %d" % total)
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialise the 832402226 calculator backend database"
    )
    parser.add_argument("--reset", action="store_true",
                        help="delete the old database file before creating the schema")
    parser.add_argument("--demo", action="store_true",
                        help="insert 3 sample rows")
    parser.add_argument("--db", default=None,
                        help="custom database file path")
    args = parser.parse_args()

    database_path = args.db or Config.DATABASE_PATH
    print("[info] database path: %s" % database_path)
    print("[info] schema statements: %d" % len(SCHEMA_STATEMENTS))

    if args.reset:
        reset_database(database_path)

    # SQLite creates the file itself; only the parent directory must exist.
    # With a bare file name such as `--db calc.db`, dirname() is empty and
    # os.makedirs("") would raise, hence the guard.
    parent_dir = os.path.dirname(database_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    init_database(database_path)
    print("[ok] table and index are ready (IF NOT EXISTS, safe to re-run)")

    if args.demo:
        inserted = insert_demo_records(database_path)
        print("[ok] inserted %d sample rows" % inserted)

    describe_schema(database_path)
    print("\nDone. You can now start the service with: python run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
