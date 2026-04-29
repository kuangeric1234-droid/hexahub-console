"""add facebook to platform enum

Revision ID: 003
Revises: 002
Create Date: 2026-04-29 12:00:00.000000
"""
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE platform ADD VALUE IF NOT EXISTS 'facebook'")


def downgrade() -> None:
    pass
