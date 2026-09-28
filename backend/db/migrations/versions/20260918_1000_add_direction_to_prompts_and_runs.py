"""add direction to prompts and runs

Revision ID: 20260918_1000
Revises: 20260911_1000
Create Date: 2026-09-18 10:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260918_1000"
down_revision = "20260911_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = shared prompt, runs regardless of direction (News, Sectors, Macro).
    # "long" / "short" = only selected when the run's direction matches (Technical, CEO).
    op.add_column("prompts", sa.Column("direction", sa.String(length=10), nullable=True))
    # Every run has a direction; existing rows default to "long" (today's only behavior).
    op.add_column(
        "runs",
        sa.Column("direction", sa.String(length=10), server_default="long", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("runs", "direction")
    op.drop_column("prompts", "direction")
