"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Enum types (created once here; all columns use create_type=False) ─────
    op.execute("CREATE TYPE campaignstatus  AS ENUM ('draft','active','paused','completed','archived')")
    op.execute("CREATE TYPE platform        AS ENUM ('linkedin','blog','instagram','xiaohongshu','wechat_moments')")
    op.execute("CREATE TYPE poststatus      AS ENUM ('pending','generating','draft','approved','rejected','scheduled','published','failed')")
    op.execute("CREATE TYPE approvaldecision AS ENUM ('pending','approved','rejected')")
    op.execute("CREATE TYPE assettype       AS ENUM ('image','video','document')")
    op.execute("CREATE TYPE agentlogstatus  AS ENUM ('running','success','failed')")
    op.execute("CREATE TYPE wordseverity    AS ENUM ('low','medium','high','critical')")

    # ── campaigns ─────────────────────────────────────────────────────────────
    op.create_table(
        "campaigns",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True),
        sa.Column("name",       sa.String(255),     nullable=False),
        sa.Column("brief",      sa.Text(),          nullable=False),
        sa.Column("objective",  sa.Text(),          nullable=False),
        sa.Column("kpis",       JSONB(),            nullable=False, server_default="{}"),
        sa.Column("start_date", sa.Date(),          nullable=False),
        sa.Column("end_date",   sa.Date(),          nullable=False),
        sa.Column("status",     sa.Enum(name="campaignstatus",  create_type=False), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # ── content_pillars ───────────────────────────────────────────────────────
    op.create_table(
        "content_pillars",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name",        sa.String(255),     nullable=False),
        sa.Column("description", sa.Text(),          nullable=True),
        sa.Column("weight",      sa.Float(),         nullable=False, server_default="1.0"),
    )

    # ── posts ─────────────────────────────────────────────────────────────────
    op.create_table(
        "posts",
        sa.Column("id",              UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id",     UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pillar_id",       UUID(as_uuid=True), sa.ForeignKey("content_pillars.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform",        sa.Enum(name="platform",         create_type=False), nullable=False),
        sa.Column("scheduled_at",    sa.DateTime(timezone=True),      nullable=True),
        sa.Column("status",          sa.Enum(name="poststatus",       create_type=False), nullable=False, server_default="pending"),
        sa.Column("copy",            sa.Text(),                        nullable=True),
        sa.Column("visual_url",      sa.String(2048),                  nullable=True),
        sa.Column("metadata_json",   JSONB(),                          nullable=False, server_default="{}"),
        sa.Column("approval_status", sa.Enum(name="approvaldecision", create_type=False), nullable=False, server_default="pending"),
        sa.Column("created_at",      sa.DateTime(timezone=True)),
        sa.Column("updated_at",      sa.DateTime(timezone=True)),
    )

    # ── assets ────────────────────────────────────────────────────────────────
    # The `embedding` column uses the pgvector extension (enabled above).
    # We use raw SQL for this column because SQLAlchemy's op.create_table()
    # doesn't natively emit the `vector(1536)` type string.
    op.create_table(
        "assets",
        sa.Column("id",                UUID(as_uuid=True), primary_key=True),
        sa.Column("type",              sa.Enum(name="assettype", create_type=False), nullable=False),
        sa.Column("url",               sa.String(2048),  nullable=False),
        sa.Column("tags",              ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("performance_score", sa.Float(),       nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True)),
    )
    # Add vector column separately via raw DDL
    op.execute("ALTER TABLE assets ADD COLUMN embedding vector(1536)")

    # ── approvals ─────────────────────────────────────────────────────────────
    op.create_table(
        "approvals",
        sa.Column("id",        UUID(as_uuid=True), primary_key=True),
        sa.Column("post_id",   UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer",  sa.String(255),     nullable=False),
        sa.Column("decision",  sa.Enum(name="approvaldecision", create_type=False), nullable=False, server_default="pending"),
        sa.Column("feedback",  sa.Text(),          nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True)),
    )

    # ── agent_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "agent_logs",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_name",  sa.String(255),     nullable=False),
        sa.Column("task",        sa.String(255),     nullable=False),
        sa.Column("input_json",  JSONB(),            nullable=False, server_default="{}"),
        sa.Column("output_json", JSONB(),            nullable=True),
        sa.Column("status",      sa.Enum(name="agentlogstatus", create_type=False), nullable=False, server_default="running"),
        sa.Column("duration_ms", sa.Integer(),       nullable=True),
        sa.Column("timestamp",   sa.DateTime(timezone=True)),
    )

    # ── metrics ───────────────────────────────────────────────────────────────
    op.create_table(
        "metrics",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True),
        sa.Column("post_id",     UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform",    sa.Enum(name="platform", create_type=False), nullable=False),
        sa.Column("reach",       sa.Integer(), nullable=True),
        sa.Column("engagement",  sa.Integer(), nullable=True),
        sa.Column("ctr",         sa.Float(),   nullable=True),
        sa.Column("conversions", sa.Integer(), nullable=True),
        sa.Column("fetched_at",  sa.DateTime(timezone=True)),
    )

    # ── sensitive_words ───────────────────────────────────────────────────────
    op.create_table(
        "sensitive_words",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True),
        sa.Column("word",       sa.String(255), nullable=False),
        sa.Column("language",   sa.String(10),  nullable=False, server_default="en"),
        sa.Column("severity",   sa.Enum(name="wordseverity", create_type=False), nullable=False, server_default="medium"),
        sa.Column("category",   sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.create_index("ix_posts_campaign_id",    "posts",      ["campaign_id"])
    op.create_index("ix_posts_platform",       "posts",      ["platform"])
    op.create_index("ix_posts_scheduled_at",   "posts",      ["scheduled_at"])
    op.create_index("ix_posts_approval_status","posts",      ["approval_status"])
    op.create_index("ix_agent_logs_agent_name","agent_logs", ["agent_name"])
    op.create_index("ix_agent_logs_timestamp", "agent_logs", ["timestamp"])
    op.create_index("ix_metrics_post_id",      "metrics",    ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_metrics_post_id",       table_name="metrics")
    op.drop_index("ix_agent_logs_timestamp",  table_name="agent_logs")
    op.drop_index("ix_agent_logs_agent_name", table_name="agent_logs")
    op.drop_index("ix_posts_approval_status", table_name="posts")
    op.drop_index("ix_posts_scheduled_at",    table_name="posts")
    op.drop_index("ix_posts_platform",        table_name="posts")
    op.drop_index("ix_posts_campaign_id",     table_name="posts")

    op.drop_table("sensitive_words")
    op.drop_table("metrics")
    op.drop_table("agent_logs")
    op.drop_table("approvals")
    op.drop_table("assets")
    op.drop_table("posts")
    op.drop_table("content_pillars")
    op.drop_table("campaigns")

    op.execute("DROP TYPE IF EXISTS wordseverity")
    op.execute("DROP TYPE IF EXISTS agentlogstatus")
    op.execute("DROP TYPE IF EXISTS assettype")
    op.execute("DROP TYPE IF EXISTS approvaldecision")
    op.execute("DROP TYPE IF EXISTS poststatus")
    op.execute("DROP TYPE IF EXISTS platform")
    op.execute("DROP TYPE IF EXISTS campaignstatus")
    op.execute("DROP EXTENSION IF EXISTS vector")
