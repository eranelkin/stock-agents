"""add ibk_session_id to runs

Revision ID: 20260909_1000
Revises: 20260803_1000
Create Date: 2026-09-09 10:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260909_1000"
down_revision = "20260803_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("ibk_session_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "ibk_session_id")
