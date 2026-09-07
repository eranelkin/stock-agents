"""add_entry_window_to_scan_results

Revision ID: 20260907_1000
Revises: 20260905_1000
Create Date: 2026-09-07

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_1000"
down_revision: str | None = "20260905_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scan_results", sa.Column("entry_window_low", sa.Float(), nullable=True))
    op.add_column("scan_results", sa.Column("entry_window_high", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("scan_results", "entry_window_high")
    op.drop_column("scan_results", "entry_window_low")
