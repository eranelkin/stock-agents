"""add_is_active_to_prompts

Revision ID: c198bf666070
Revises: e38104261395
Create Date: 2026-06-03 10:25:05.213203

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'c198bf666070'
down_revision: str | None = 'e38104261395'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true")


def downgrade() -> None:
    op.drop_column("prompts", "is_active")
