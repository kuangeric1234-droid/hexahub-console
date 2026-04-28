"""add users, post_versions, ad_creative_runs; name column on assets

Revision ID: 002
Revises: 001
Create Date: 2026-04-27 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",              UUID(as_uuid=True), primary_key=True),
        sa.Column("email",           sa.String(255),     nullable=False),
        sa.Column("hashed_password", sa.String(255),     nullable=False),
        sa.Column("full_name",       sa.String(255),     nullable=True),
        sa.Column("role",            sa.String(50),      nullable=False, server_default="member"),
        sa.Column("is_active",       sa.Boolean(),       nullable=False, server_default="true"),
        sa.Column("created_at",      sa.DateTime(timezone=True)),
        sa.Column("last_login_at",   sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── post_versions ─────────────────────────────────────────────────────────
    op.create_table(
        "post_versions",
        sa.Column("id",             UUID(as_uuid=True), primary_key=True),
        sa.Column("post_id",        UUID(as_uuid=True),
                  sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(),       nullable=False),
        sa.Column("copy",           sa.Text(),          nullable=True),
        sa.Column("visual_url",     sa.String(2048),    nullable=True),
        sa.Column("scheduled_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("edited_by",      sa.String(255),     nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True)),
    )
    op.create_index("ix_post_versions_post_id", "post_versions", ["post_id"])

    # ── ad_creative_runs ──────────────────────────────────────────────────────
    op.create_table(
        "ad_creative_runs",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id",     UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_id", UUID(as_uuid=True),
                  sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform",    sa.String(50),  nullable=False),
        sa.Column("input_json",  JSONB(),         nullable=False, server_default="{}"),
        sa.Column("output_json", JSONB(),         nullable=False, server_default="{}"),
        sa.Column("created_at",  sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ad_creative_runs_user_id",     "ad_creative_runs", ["user_id"])
    op.create_index("ix_ad_creative_runs_campaign_id", "ad_creative_runs", ["campaign_id"])

    # ── assets: add name column ───────────────────────────────────────────────
    op.add_column("assets", sa.Column("name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "name")
    op.drop_index("ix_ad_creative_runs_campaign_id", table_name="ad_creative_runs")
    op.drop_index("ix_ad_creative_runs_user_id",     table_name="ad_creative_runs")
    op.drop_table("ad_creative_runs")
    op.drop_index("ix_post_versions_post_id", table_name="post_versions")
    op.drop_table("post_versions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
