"""add_model_names_to_runs

Revision ID: b7e2d4f83a19
Revises: a3f1c9e72d04
Create Date: 2026-06-10 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2d4f83a19'
down_revision: str | None = 'a3f1c9e72d04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS model_names JSONB NULL")


def downgrade() -> None:
    op.drop_column("runs", "model_names")
