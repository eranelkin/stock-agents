"""add is_favorite to runs

Revision ID: 20260911_1000
Revises: 20260909_1000
Create Date: 2026-09-11 10:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260911_1000"
down_revision = "20260909_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("is_favorite", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("runs", "is_favorite")
