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
HEAD = "c198bf666070"

# Columns that were added by specific revisions (after the initial schema).
# Used to detect how far a legacy DB has already progressed.
# Format: (table, column, revision_that_added_it)
REVISION_MARKERS: list[tuple[str, str, str]] = [
    ("runs",    "output_dir", "e38104261395"),
    ("prompts", "is_active",  "c198bf666070"),
]


def _alembic_cfg() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    return cfg


async def _prepare_db() -> None:
    """Detect DB state and stamp Alembic if the DB is not yet tracked."""
    engine = create_async_engine(settings.database_url)
    stamp_to: str | None = None

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
                return

            # ── Case 2: Fresh database (no tables at all) ──────────────────
            has_runs = await conn.scalar(text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_name = 'runs'"
                ")"
            ))
            if not has_runs:
                _log("Fresh database detected — all migrations will run from scratch")
                return

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
                    stamp_to = revision
                    break
            else:
                # None of the later columns exist — legacy DB is at base schema
                stamp_to = "0001"

    finally:
        await engine.dispose()

    _log(f"Stamping database at revision: {stamp_to}")
    alembic_cmd.stamp(_alembic_cfg(), stamp_to)
    _log(f"Stamped at {stamp_to}")


async def _run_upgrade() -> None:
    """Run alembic upgrade head (always safe — no-op if already at head)."""
    _log("Running: alembic upgrade head")
    alembic_cmd.upgrade(_alembic_cfg(), "head")


def _log(msg: str) -> None:
    print(f"  {msg}")


async def main() -> None:
    print()
    print("=" * 50)
    print("  Stock-Agents — Database Migration")
    print("=" * 50)
    print()

    try:
        await _prepare_db()
        await _run_upgrade()
    except Exception as exc:
        print(f"\n  ERROR: {exc}")
        sys.exit(1)

    print()
    print("  Database is up to date.")
    print()


if __name__ == "__main__":
    try:
        # Try to get the current event loop
        loop = asyncio.get_running_loop()
        # If we're already in an event loop, create a task
        import asyncio
        task = asyncio.create_task(main())
        # We can't await here since we're in a sync context, so we need a different approach
        # Use asyncio.ensure_future and run until complete on a new loop
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.run(main())
    except RuntimeError:
        # No event loop running, safe to use asyncio.run()
        asyncio.run(main())
