"""add max gain to scan results

Revision ID: 41a9d47c4790
Revises: aed22f5dcb56
Create Date: 2026-09-28 15:41:23.050884

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '41a9d47c4790'
down_revision: str | None = 'aed22f5dcb56'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS max_gain_pct DOUBLE PRECISION")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS max_gain_time TIMESTAMPTZ")


def downgrade() -> None:
    op.drop_column("scan_results", "max_gain_time")
    op.drop_column("scan_results", "max_gain_pct")
