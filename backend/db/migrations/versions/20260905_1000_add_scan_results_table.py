"""add_scan_results_table

Revision ID: 20260905_1000
Revises: 20260904_1000
Create Date: 2026-09-05

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_1000"
down_revision: str | None = "20260904_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.JSON(), nullable=False),
        sa.Column("entry_low", sa.Float(), nullable=True),
        sa.Column("entry_high", sa.Float(), nullable=True),
        sa.Column("entry_time_start", sa.String(length=10), nullable=True),
        sa.Column("entry_time_end", sa.String(length=10), nullable=True),
        sa.Column("sl_low", sa.Float(), nullable=True),
        sa.Column("sl_high", sa.Float(), nullable=True),
        sa.Column("tp_low", sa.Float(), nullable=True),
        sa.Column("tp_high", sa.Float(), nullable=True),
        sa.Column("fill_status", sa.String(length=20), nullable=False),
        sa.Column("fill_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fill_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(length=20), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("r_multiple", sa.Float(), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "ticker", name="uq_scan_results_run_ticker"),
    )


def downgrade() -> None:
    op.drop_table("scan_results")
