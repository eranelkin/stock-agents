"""add search_depth to prompts

Revision ID: 20260803_1000
Revises: a1b2c3d4e5f6
Create Date: 2026-08-03 10:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260803_1000"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prompts", sa.Column("search_depth", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("prompts", "search_depth")
