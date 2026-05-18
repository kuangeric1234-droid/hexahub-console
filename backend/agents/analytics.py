"""
AnalyticsAgent — pulls Meta Ads insights and writes them to the metrics table.

Input:  campaign_id + date range
Output: per-campaign metric rows written to DB; summary string returned

Calls MetaAdsService.get_insights() for every AdCampaign row linked to the
given campaign_id.  Results are upserted into the metrics table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.db.models import AdCampaign, Metric, Platform, Post
from backend.llm.client import LLMProvider

log = structlog.get_logger()


class AnalyticsInput(BaseModel):
    campaign_id: UUID
    start_date:  datetime
    end_date:    datetime
    platforms:   list[Platform]


class AnalyticsOutput(BaseModel):
    campaign_id:     UUID
    period_start:    datetime
    period_end:      datetime
    metrics_by_post: list[dict]
    summary:         str = ""


class AnalyticsAgent(BaseAgent[AnalyticsInput, AnalyticsOutput]):
    agent_name       = "analytics_agent"
    default_provider = LLMProvider.ANTHROPIC

    async def run(
        self,
        input_data: AnalyticsInput,
        db: Optional[AsyncSession] = None,
    ) -> AnalyticsOutput:
        if db is None:
            raise ValueError("AnalyticsAgent requires a DB session")

        from backend.services.meta_ads import MetaAdsService

        # Load Meta Ads service — skip gracefully if not connected
        try:
            svc = await MetaAdsService.from_db(db)
        except ValueError as exc:
            log.warning("analytics_agent_meta_not_connected", reason=str(exc))
            return AnalyticsOutput(
                campaign_id  = input_data.campaign_id,
                period_start = input_data.start_date,
                period_end   = input_data.end_date,
                metrics_by_post = [],
                summary      = f"Meta not connected: {exc}",
            )

        # Find all AdCampaign rows for this content campaign
        result  = await db.execute(
            select(AdCampaign).where(AdCampaign.campaign_id == input_data.campaign_id)
        )
        ad_rows = result.scalars().all()

        if not ad_rows:
            return AnalyticsOutput(
                campaign_id  = input_data.campaign_id,
                period_start = input_data.start_date,
                period_end   = input_data.end_date,
                metrics_by_post = [],
                summary      = "No Meta Ads campaigns linked to this content campaign.",
            )

        # Get a representative post to attach metrics to
        post_q = await db.execute(
            select(Post).where(Post.campaign_id == input_data.campaign_id).limit(1)
        )
        post = post_q.scalar_one_or_none()

        metrics_by_post: list[dict] = []
        now = datetime.now(timezone.utc)

        for ad in ad_rows:
            try:
                insights = await svc.get_insights(ad.meta_campaign_id)
            except Exception as exc:
                log.error("analytics_agent_insights_failed",
                          meta_campaign_id=ad.meta_campaign_id, error=str(exc))
                continue

            row = {
                "meta_campaign_id": ad.meta_campaign_id,
                "reach":            insights.reach,
                "impressions":      insights.impressions,
                "clicks":           insights.clicks,
                "ctr":              insights.ctr,
                "spend_aud":        insights.spend_aud,
                "leads":            insights.leads,
                "cpl_aud":          insights.cpl_aud,
            }
            metrics_by_post.append(row)

            # Write to metrics table (columns match Metric model exactly)
            if post:
                metric = Metric(
                    post_id    = post.id,
                    platform   = Platform.facebook,
                    reach      = insights.reach,
                    engagement = insights.clicks,
                    ctr        = insights.ctr,
                    conversions= insights.leads,
                    fetched_at = now,
                )
                db.add(metric)

            ad.synced_at  = now
            ad.updated_at = now

        await db.flush()

        total_leads = sum(r["leads"] for r in metrics_by_post)
        total_spend = sum(r["spend_aud"] for r in metrics_by_post)
        summary = (
            f"Synced {len(metrics_by_post)} Meta Ads campaign(s). "
            f"Total leads: {total_leads}, total spend: AUD ${total_spend:.2f}."
        )

        return AnalyticsOutput(
            campaign_id     = input_data.campaign_id,
            period_start    = input_data.start_date,
            period_end      = input_data.end_date,
            metrics_by_post = metrics_by_post,
            summary         = summary,
        )
