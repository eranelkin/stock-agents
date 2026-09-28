"""add setup by price fields to scan results

Revision ID: ed20857d65b3
Revises: f183215ec313
Create Date: 2026-09-28 16:12:42.356073

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'ed20857d65b3'
down_revision: str | None = 'f183215ec313'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS price_fill_time TIMESTAMPTZ")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS price_fill_price DOUBLE PRECISION")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS price_best_price DOUBLE PRECISION")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS price_best_time TIMESTAMPTZ")
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS price_gain_pct DOUBLE PRECISION")


def downgrade() -> None:
    op.drop_column("scan_results", "price_gain_pct")
    op.drop_column("scan_results", "price_best_time")
    op.drop_column("scan_results", "price_best_price")
    op.drop_column("scan_results", "price_fill_price")
    op.drop_column("scan_results", "price_fill_time")
