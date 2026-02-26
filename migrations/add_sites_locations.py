# -*- coding: utf-8 -*-
"""
Migration: add_sites_locations

Extends the ``sites`` table with additional identification and descriptive
columns, and creates the new ``locations`` table that supports a
self-referential hierarchy within each site.

New columns on ``sites``:
  - code        VARCHAR(30) UNIQUE   – short human-readable identifier
  - country     VARCHAR(120)         – country of the site
  - address     VARCHAR(255)         – physical address
  - description TEXT                 – optional notes

New table ``locations``:
  - id           INTEGER PRIMARY KEY
  - name         VARCHAR(120) NOT NULL
  - code         VARCHAR(30)          – optional, unique within (site_id, code)
  - site_id      INTEGER FK → sites.id
  - parent_id    INTEGER FK → locations.id  (self-referential, nullable)
  - floor        VARCHAR(30)
  - description  TEXT
  - metadata_json TEXT                – JSON blob for extensible attributes
  - created_at   DATETIME
  - updated_at   DATETIME

Usage:
    python -m migrations.add_sites_locations [DATABASE_URL]

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
    existing_tables = inspector.get_table_names()

    # ------------------------------------------------------------------
    # 1. Extend the sites table with new optional columns
    # ------------------------------------------------------------------
    if "sites" in existing_tables:
        existing_columns = {col["name"] for col in inspector.get_columns("sites")}
        new_site_columns = {
            "code": "VARCHAR(30)",
            "country": "VARCHAR(120)",
            "address": "VARCHAR(255)",
            "description": "TEXT",
        }
        with engine.begin() as conn:
            for col_name, col_def in new_site_columns.items():
                if col_name not in existing_columns:
                    conn.execute(
                        text(f"ALTER TABLE sites ADD COLUMN {col_name} {col_def}")
                    )
                    print(f"  added column: sites.{col_name}")
                else:
                    print(f"  column sites.{col_name} already exists – skipping.")
    else:
        print("  sites table does not exist – will be created with full schema.")

    # ------------------------------------------------------------------
    # 2. Create the locations table if it does not exist
    # ------------------------------------------------------------------
    if "locations" not in existing_tables:
        Base.metadata.tables["locations"].create(bind=engine)
        print("  created table: locations")
    else:
        print("  locations table already exists – skipping creation.")


if __name__ == "__main__":
    db_url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    print("Running migration: add_sites_locations")
    run(db_url_arg)
    print("Done.")
