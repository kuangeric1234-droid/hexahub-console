"""add ad_campaigns table

Revision ID: 006
Revises: 005
Create Date: 2026-05-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: str = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_campaigns",
        sa.Column("id",               sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("campaign_id",      sa.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meta_campaign_id", sa.String(255), nullable=False, unique=True),
        sa.Column("meta_adset_id",    sa.String(255), nullable=True),
        sa.Column("meta_ad_id",       sa.String(255), nullable=True),
        sa.Column("status",           sa.String(50),  nullable=False, server_default="PAUSED"),
        sa.Column("daily_budget",     sa.Integer,     nullable=True),
        sa.Column("objective",        sa.String(100), nullable=True),
        sa.Column("targeting_summary",sa.Text,        nullable=True),
        sa.Column("synced_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at",       sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ad_campaigns_meta_campaign_id", "ad_campaigns", ["meta_campaign_id"])
    op.create_index("ix_ad_campaigns_campaign_id",      "ad_campaigns", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_ad_campaigns_campaign_id",      table_name="ad_campaigns")
    op.drop_index("ix_ad_campaigns_meta_campaign_id", table_name="ad_campaigns")
    op.drop_table("ad_campaigns")
