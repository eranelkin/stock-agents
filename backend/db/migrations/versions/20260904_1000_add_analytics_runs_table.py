"""add_analytics_runs_table

Revision ID: 20260904_1000
Revises: 20260803_1000
Create Date: 2026-09-04

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_1000"
down_revision: str | None = "20260803_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )


def downgrade() -> None:
    op.drop_table("analytics_runs")
