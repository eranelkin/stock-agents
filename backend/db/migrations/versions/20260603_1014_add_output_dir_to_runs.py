"""add_output_dir_to_runs

Revision ID: e38104261395
Revises: 0002
Create Date: 2026-06-03 10:14:56.352595

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'e38104261395'
down_revision: str | None = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("output_dir", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "output_dir")
