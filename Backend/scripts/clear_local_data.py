"""Clear local TokenPilot data without changing the database schema.

Usage:
    python scripts/clear_local_data.py
    python scripts/clear_local_data.py --yes

This preserves the Alembic revision table so migrations remain intact.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.core.database import engine


PRESERVED_TABLES = {"alembic_version"}


def clear_database() -> list[str]:
    inspector = inspect(engine)
    tables = [table for table in inspector.get_table_names() if table not in PRESERVED_TABLES]
    if not tables:
        return []

    # PostgreSQL CASCADE handles all foreign-key dependencies while preserving
    # every table, index, constraint, and migration record.
    quoted_tables = ", ".join(f'public."{table.replace(chr(34), chr(34) + chr(34))}"' for table in tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))
    return tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear local TokenPilot data")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()
    tables = [table for table in inspect(engine).get_table_names() if table not in PRESERVED_TABLES]
    print("Tables to clear:", ", ".join(tables) if tables else "none")
    if not args.yes:
        confirmation = input("Type CLEAR to continue: ")
        if confirmation != "CLEAR":
            print("Cancelled.")
            raise SystemExit(0)
    cleared = clear_database()
    print(f"Cleared {len(cleared)} table(s). Schema and Alembic history preserved.")
