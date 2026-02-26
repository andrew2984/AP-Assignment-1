# -*- coding: utf-8 -*-
"""
Migration: add_assignments

Creates the `assignments` and `assignment_approvers` tables and adds the
`assignment_id` column to `access_requests` to support the assignment and
approver data models.

Usage:
    python -m migrations.add_assignments [DATABASE_URL]

If DATABASE_URL is omitted the value of the DATABASE_URL environment variable
is used, falling back to ``sqlite:///app.db``.
"""

import os
import sys

from sqlalchemy import create_engine, inspect, text

# Ensure the project root is on the path when running as a script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import Base  # noqa: E402 – import after path fix
import app.models  # noqa: F401 – registers all models with Base.metadata


def run(db_url: str | None = None) -> None:
    db_url = db_url or os.getenv("DATABASE_URL", "sqlite:///app.db")
    engine = create_engine(
        db_url,
        future=True,
        connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {},
    )

    inspector = inspect(engine)
    existing = inspector.get_table_names()

    # Create new tables that do not yet exist.
    target_tables = {"assignments", "assignment_approvers"}
    tables_to_create = {
        name: Base.metadata.tables[name]
        for name in target_tables
        if name not in existing
    }

    if tables_to_create:
        Base.metadata.create_all(bind=engine, tables=list(tables_to_create.values()))
        for name in tables_to_create:
            print(f"  created table: {name}")
    else:
        print("  assignment tables already exist – skipping creation.")

    # Add assignment_id column to access_requests if it is missing.
    if "access_requests" in existing:
        existing_columns = {col["name"] for col in inspector.get_columns("access_requests")}
        if "assignment_id" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE access_requests "
                        "ADD COLUMN assignment_id INTEGER REFERENCES assignments(id)"
                    )
                )
            print("  added column: access_requests.assignment_id")
        else:
            print("  column access_requests.assignment_id already exists – skipping.")


if __name__ == "__main__":
    db_url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print("Running migration: add_assignments")
    run(db_url_arg)
    print("Done.")
