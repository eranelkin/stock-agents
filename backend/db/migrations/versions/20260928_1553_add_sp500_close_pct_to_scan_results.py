"""add sp500 close pct to scan results

Revision ID: b3018edec8fd
Revises: 9617b1d152e9
Create Date: 2026-09-28 15:53:17.330667

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'b3018edec8fd'
down_revision: str | None = '9617b1d152e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS sp500_close_pct DOUBLE PRECISION")


def downgrade() -> None:
    op.drop_column("scan_results", "sp500_close_pct")
