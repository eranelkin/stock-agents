"""add ceo_analysis table

Revision ID: 20260925_1000
Revises: 20260924_1100
Create Date: 2026-09-25 10:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260925_1000"
down_revision = "20260924_1100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ceo_analysis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("success_setup", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("max_gain_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("annotation_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "ticker", "model_name", name="uq_ceo_analysis_run_ticker_model"),
    )
    op.create_index("ix_ceo_analysis_run_id", "ceo_analysis", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_ceo_analysis_run_id", table_name="ceo_analysis")
    op.drop_table("ceo_analysis")
