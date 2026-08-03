"""add_thinking_and_search_depth_to_models

Revision ID: f3c8d1e45a27
Revises: e5a7b9c34f12
Create Date: 2026-08-02 10:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision: str = 'f3c8d1e45a27'
down_revision: str | None = 'e5a7b9c34f12'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS thinking_budget_tokens INTEGER NULL")
    op.execute("ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS search_depth VARCHAR(20) NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE ai_models DROP COLUMN IF EXISTS thinking_budget_tokens")
    op.execute("ALTER TABLE ai_models DROP COLUMN IF EXISTS search_depth")
