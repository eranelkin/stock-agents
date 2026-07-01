#!/usr/bin/env python3
"""Smart database migration script for Stock-Agents.

Detects the current state of the database and applies all pending Alembic
migrations safely — whether the DB is brand new, a legacy DB from before
Alembic was introduced, or already partially migrated.

Usage (from the project root):
    python scripts/migrate.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path and is the working directory
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command as alembic_cmd
from alembic.config import Config

from backend.config import settings

# The current head revision — update this when new migrations are added
HEAD = "e5a7b9c34f12"

# Columns that were added by specific revisions (after the initial schema).
# Used to detect how far a legacy DB has already progressed.
# Format: (table, column, revision_that_added_it)
REVISION_MARKERS: list[tuple[str, str, str]] = [
    ("runs",    "output_dir",  "e38104261395"),
    ("prompts", "is_active",   "c198bf666070"),
    ("runs",    "model_names", "b7e2d4f83a19"),
]


def _alembic_cfg() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    return cfg


async def _detect_db_state() -> str | None:
    """Detect DB state and return the revision to stamp, or None if no stamp needed."""
    engine = create_async_engine(settings.database_url)

    try:
        async with engine.connect() as conn:
            # ── Case 1: Alembic already tracking this DB ──────────────────
            has_alembic = await conn.scalar(text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name = 'alembic_version'"
                ")"
            ))
            if has_alembic:
                rev = await conn.scalar(text(
                    "SELECT version_num FROM alembic_version LIMIT 1"
                ))
                _log(f"Alembic already initialized — current revision: {rev or 'none'}")
                return None

            # ── Case 2: Fresh database (no tables at all) ──────────────────
            has_runs = await conn.scalar(text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name = 'runs'"
                ")"
            ))
            if not has_runs:
                _log("Fresh database detected — all migrations will run from scratch")
                return None

            # ── Case 3: Legacy DB (tables exist, Alembic never ran) ────────
            _log("Legacy database detected (tables exist, no Alembic tracking)")
            _log("Inspecting schema to determine the correct starting point...")

            def _get_columns(sync_conn: object, table: str) -> set[str]:
                return {c["name"] for c in inspect(sync_conn).get_columns(table)}  # type: ignore[arg-type]

            col_cache: dict[str, set[str]] = {}
            for table, column, _ in REVISION_MARKERS:
                if table not in col_cache:
                    col_cache[table] = await conn.run_sync(
                        lambda c, t=table: _get_columns(c, t)
                    )

            # Walk markers from newest to oldest to find the highest applied revision
            for table, column, revision in reversed(REVISION_MARKERS):
                if column in col_cache[table]:
                    return revision

            # None of the later columns exist — legacy DB is at base schema
            return "0001"

    finally:
        await engine.dispose()


def _log(msg: str) -> None:
    print(f"  {msg}")


def main() -> None:
    print()
    print("=" * 50)
    print("  Stock-Agents — Database Migration")
    print("=" * 50)
    print()

    try:
        stamp_to = asyncio.run(_detect_db_state())
        if stamp_to is not None:
            _log(f"Stamping database at revision: {stamp_to}")
            alembic_cmd.stamp(_alembic_cfg(), stamp_to)
            _log(f"Stamped at {stamp_to}")

        _log("Running: alembic upgrade head")
        alembic_cmd.upgrade(_alembic_cfg(), "head")
    except Exception as exc:
        print(f"\n  ERROR: {exc}")
        sys.exit(1)

    print()
    print("  Database is up to date.")
    print()


if __name__ == "__main__":
    main()
