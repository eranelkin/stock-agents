"""merge analytics and main migration heads

Revision ID: aed22f5dcb56
Revises: 20260907_1000, 20260924_1100
Create Date: 2026-09-28 12:52:27.222765

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'aed22f5dcb56'
down_revision: str | None = ('20260907_1000', '20260924_1100')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
