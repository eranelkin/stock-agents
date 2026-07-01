"""add_input_schema_to_prompts

Revision ID: e5a7b9c34f12
Revises: d4f6a8c21e93
Create Date: 2026-07-01 10:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision: str = 'e5a7b9c34f12'
down_revision: str | None = 'd4f6a8c21e93'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS input_schema JSONB NULL")


def downgrade() -> None:
    op.drop_column("prompts", "input_schema")
