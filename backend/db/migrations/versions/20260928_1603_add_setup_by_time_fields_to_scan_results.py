"""add setup by time fields to scan results

Revision ID: f183215ec313
Revises: b3018edec8fd
Create Date: 2026-09-28 16:03:19.960553

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'f183215ec313'
down_revision: str | None = 'b3018edec8fd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS action_time TIMESTAMPTZ")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS action_fill_price DOUBLE PRECISION")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS action_best_price DOUBLE PRECISION")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS action_best_time TIMESTAMPTZ")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS action_gain_pct DOUBLE PRECISION")


def downgrade() -> None:
    op.drop_column("scan_results", "action_gain_pct")
    op.drop_column("scan_results", "action_best_time")
    op.drop_column("scan_results", "action_best_price")
    op.drop_column("scan_results", "action_fill_price")
    op.drop_column("scan_results", "action_time")
