"""add max gain price to scan results

Revision ID: 9617b1d152e9
Revises: 41a9d47c4790
Create Date: 2026-09-28 15:47:40.170229

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '9617b1d152e9'
down_revision: str | None = '41a9d47c4790'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scan_results ADD COLUMN IF NOT EXISTS max_gain_price DOUBLE PRECISION")


def downgrade() -> None:
    op.drop_column("scan_results", "max_gain_price")
