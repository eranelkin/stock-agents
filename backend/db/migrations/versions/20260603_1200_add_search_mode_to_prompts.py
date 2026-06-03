"""add_search_mode_to_prompts

Revision ID: a3f1c9e72d04
Revises: c198bf666070
Create Date: 2026-06-03 12:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f1c9e72d04'
down_revision: str | None = 'c198bf666070'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS search_mode VARCHAR(20) NULL")


def downgrade() -> None:
    op.drop_column("prompts", "search_mode")
