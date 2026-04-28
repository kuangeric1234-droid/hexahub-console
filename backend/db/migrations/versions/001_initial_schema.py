"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE campaignstatus  AS ENUM ('draft','active','paused','completed','archived');
        CREATE TYPE platform        AS ENUM ('linkedin','blog','instagram','xiaohongshu','wechat_moments');
        CREATE TYPE poststatus      AS ENUM ('pending','generating','draft','approved','rejected','scheduled','published','failed');
        CREATE TYPE approvaldecision AS ENUM ('pending','approved','rejected');
        CREATE TYPE assettype       AS ENUM ('image','video','document');
        CREATE TYPE agentlogstatus  AS ENUM ('running','success','failed');
        CREATE TYPE wordseverity    AS ENUM ('low','medium','high','critical');

        CREATE TABLE campaigns (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name       VARCHAR(255) NOT NULL,
            brief      TEXT NOT NULL,
            objective  TEXT NOT NULL,
            kpis       JSONB NOT NULL DEFAULT '{}',
            start_date DATE NOT NULL,
            end_date   DATE NOT NULL,
            status     campaignstatus NOT NULL DEFAULT 'draft',
            created_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ
        );

        CREATE TABLE content_pillars (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            name        VARCHAR(255) NOT NULL,
            description TEXT,
            weight      FLOAT NOT NULL DEFAULT 1.0
        );

        CREATE TABLE posts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            pillar_id       UUID REFERENCES content_pillars(id) ON DELETE SET NULL,
            platform        platform NOT NULL,
            scheduled_at    TIMESTAMPTZ,
            status          poststatus NOT NULL DEFAULT 'pending',
            copy            TEXT,
            visual_url      VARCHAR(2048),
            metadata_json   JSONB NOT NULL DEFAULT '{}',
            approval_status approvaldecision NOT NULL DEFAULT 'pending',
            created_at      TIMESTAMPTZ,
            updated_at      TIMESTAMPTZ
        );

        CREATE TABLE assets (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type              assettype NOT NULL,
            url               VARCHAR(2048) NOT NULL,
            tags              TEXT[] NOT NULL DEFAULT '{}',
            performance_score FLOAT,
            created_at        TIMESTAMPTZ
        );

        CREATE TABLE approvals (
            id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id   UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            reviewer  VARCHAR(255) NOT NULL,
            decision  approvaldecision NOT NULL DEFAULT 'pending',
            feedback  TEXT,
            timestamp TIMESTAMPTZ
        );

        CREATE TABLE agent_logs (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_name  VARCHAR(255) NOT NULL,
            task        VARCHAR(255) NOT NULL,
            input_json  JSONB NOT NULL DEFAULT '{}',
            output_json JSONB,
            status      agentlogstatus NOT NULL DEFAULT 'running',
            duration_ms INTEGER,
            timestamp   TIMESTAMPTZ
        );

        CREATE TABLE metrics (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id     UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
            platform    platform NOT NULL,
            reach       INTEGER,
            engagement  INTEGER,
            ctr         FLOAT,
            conversions INTEGER,
            fetched_at  TIMESTAMPTZ
        );

        CREATE TABLE sensitive_words (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            word       VARCHAR(255) NOT NULL,
            language   VARCHAR(10) NOT NULL DEFAULT 'en',
            severity   wordseverity NOT NULL DEFAULT 'medium',
            category   VARCHAR(100),
            created_at TIMESTAMPTZ
        );

        CREATE INDEX ix_posts_campaign_id     ON posts(campaign_id);
        CREATE INDEX ix_posts_platform        ON posts(platform);
        CREATE INDEX ix_posts_scheduled_at    ON posts(scheduled_at);
        CREATE INDEX ix_posts_approval_status ON posts(approval_status);
        CREATE INDEX ix_agent_logs_agent_name ON agent_logs(agent_name);
        CREATE INDEX ix_agent_logs_timestamp  ON agent_logs(timestamp);
        CREATE INDEX ix_metrics_post_id       ON metrics(post_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS metrics;
        DROP TABLE IF EXISTS agent_logs;
        DROP TABLE IF EXISTS approvals;
        DROP TABLE IF EXISTS assets;
        DROP TABLE IF EXISTS posts;
        DROP TABLE IF EXISTS content_pillars;
        DROP TABLE IF EXISTS campaigns;
        DROP TYPE IF EXISTS wordseverity;
        DROP TYPE IF EXISTS agentlogstatus;
        DROP TYPE IF EXISTS assettype;
        DROP TYPE IF EXISTS approvaldecision;
        DROP TYPE IF EXISTS poststatus;
        DROP TYPE IF EXISTS platform;
        DROP TYPE IF EXISTS campaignstatus;
    """)
