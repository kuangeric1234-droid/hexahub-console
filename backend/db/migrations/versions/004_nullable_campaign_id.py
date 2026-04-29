"""make campaign_id nullable on posts

Revision ID: 004
Revises: 003
Create Date: 2026-04-29 18:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("posts", "campaign_id", nullable=True)


def downgrade() -> None:
    op.alter_column("posts", "campaign_id", nullable=False)
