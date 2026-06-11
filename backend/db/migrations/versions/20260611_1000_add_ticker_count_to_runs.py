"""add_ticker_count_to_runs

Revision ID: c9d3e5a12b47
Revises: b7e2d4f83a19
Create Date: 2026-06-11 10:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision: str = 'c9d3e5a12b47'
down_revision: str | None = 'b7e2d4f83a19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS ticker_count INTEGER NULL")


def downgrade() -> None:
    op.drop_column("runs", "ticker_count")
