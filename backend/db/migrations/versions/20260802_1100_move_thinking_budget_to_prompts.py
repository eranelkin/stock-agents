"""move_thinking_budget_to_prompts

Revision ID: a1b2c3d4e5f6
Revises: f3c8d1e45a27
Create Date: 2026-08-02 11:00:00.000000

"""
from __future__ import annotations

from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = 'f3c8d1e45a27'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE ai_models DROP COLUMN IF EXISTS thinking_budget_tokens")
    op.execute("ALTER TABLE prompts ADD COLUMN IF NOT EXISTS thinking_budget_tokens INTEGER NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE prompts DROP COLUMN IF EXISTS thinking_budget_tokens")
    op.execute("ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS thinking_budget_tokens INTEGER NULL")
