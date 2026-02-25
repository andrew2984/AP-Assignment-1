# -*- coding: utf-8 -*-
"""
Migration: add_access_requests

Creates the `access_requests` and `access_request_status_history` tables
that implement the access-request data model.

Usage:
    python -m migrations.add_access_requests [DATABASE_URL]

If DATABASE_URL is omitted the value of the DATABASE_URL environment variable
is used, falling back to ``sqlite:///app.db``.
"""

import os
import sys

from sqlalchemy import create_engine, inspect

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

    target_tables = {"access_requests", "access_request_status_history"}
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
        print("  nothing to do – tables already exist.")


if __name__ == "__main__":
    db_url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print("Running migration: add_access_requests")
    run(db_url_arg)
    print("Done.")
