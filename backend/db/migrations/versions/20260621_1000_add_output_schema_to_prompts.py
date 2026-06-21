"""add_output_schema_to_prompts

Revision ID: d4f6a8c21e93
Revises: c9d3e5a12b47
Create Date: 2026-06-21 10:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision: str = 'd4f6a8c21e93'
down_revision: str | None = 'c9d3e5a12b47'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS output_schema JSONB NULL")


def downgrade() -> None:
    op.drop_column("prompts", "output_schema")
