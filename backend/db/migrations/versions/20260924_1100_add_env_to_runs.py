"""add env to runs

Revision ID: 20260924_1100
Revises: 20260924_1000
Create Date: 2026-09-24 11:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260924_1100"
down_revision = "20260924_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("env", sa.String(10), nullable=False, server_default="test"),
    )


def downgrade() -> None:
    op.drop_column("runs", "env")
