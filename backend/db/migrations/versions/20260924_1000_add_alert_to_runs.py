"""add alert to runs

Revision ID: 20260924_1000
Revises: 20260918_1000
Create Date: 2026-09-24 10:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260924_1000"
down_revision = "20260918_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("alert", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "alert")
