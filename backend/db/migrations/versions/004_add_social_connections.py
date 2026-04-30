"""add social_connections table

Revision ID: 004
Revises: 003
Create Date: 2026-04-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: str = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_connections",
        sa.Column("id",                 sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider",           sa.String(50),  nullable=False, unique=True),
        sa.Column("page_id",            sa.String(255), nullable=True),
        sa.Column("page_name",          sa.String(255), nullable=True),
        sa.Column("page_access_token",  sa.Text,        nullable=False),
        sa.Column("ig_user_id",         sa.String(255), nullable=True),
        sa.Column("ig_username",        sa.String(255), nullable=True),
        sa.Column("connected_at",       sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at",         sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("social_connections")
