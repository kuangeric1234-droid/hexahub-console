"""
Insights routes.

GET  /insights/summary            aggregate KPIs (reach, engagement, ctr, conversions)
GET  /insights/timeline           daily metric totals for the chart (last N days)
GET  /insights/by-platform        metrics grouped by platform
GET  /insights/by-campaign        metrics grouped by campaign
POST /insights/sync               trigger on-demand sync from Meta Graph API
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.db.models import Campaign, Metric, Platform, Post, User

log    = structlog.get_logger()
router = APIRouter(prefix="/insights", tags=["insights"])


# ── Response models ────────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    total_reach:       int
    total_engagement:  int
    avg_ctr:           float
    total_conversions: int
    posts_tracked:     int
    days:              int


class TimelinePoint(BaseModel):
    date:       str   # YYYY-MM-DD
    reach:      int
    engagement: int
    conversions:int


class TimelineResponse(BaseModel):
    points: list[TimelinePoint]
    days:   int


class PlatformRow(BaseModel):
    platform:   str
    reach:      int
    engagement: int
    conversions:int
    posts:      int


class CampaignRow(BaseModel):
    campaign_id:   str
    campaign_name: str
    reach:         int
    engagement:    int
    conversions:   int
    posts:         int


class SyncResponse(BaseModel):
    synced: int
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# ── GET /insights/summary ──────────────────────────────────────────────────────

@router.get("/summary", response_model=SummaryResponse, summary="Aggregate KPIs")
async def get_summary(
    days: int        = Query(default=30, ge=1, le=365),
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
) -> SummaryResponse:
    since = _since(days)

    row = await db.execute(
        select(
            func.coalesce(func.sum(Metric.reach),       0).label("total_reach"),
            func.coalesce(func.sum(Metric.engagement),  0).label("total_engagement"),
            func.coalesce(func.avg(Metric.ctr),         0).label("avg_ctr"),
            func.coalesce(func.sum(Metric.conversions), 0).label("total_conversions"),
            func.count(Metric.post_id.distinct()).label("posts_tracked"),
        ).where(Metric.fetched_at >= since)
    )
    r = row.one()
    return SummaryResponse(
        total_reach      = int(r.total_reach),
        total_engagement = int(r.total_engagement),
        avg_ctr          = round(float(r.avg_ctr or 0), 4),
        total_conversions= int(r.total_conversions),
        posts_tracked    = int(r.posts_tracked),
        days             = days,
    )


# ── GET /insights/timeline ─────────────────────────────────────────────────────

@router.get("/timeline", response_model=TimelineResponse, summary="Daily metrics for chart")
async def get_timeline(
    days: int        = Query(default=30, ge=1, le=365),
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
) -> TimelineResponse:
    since = _since(days)

    rows = await db.execute(
        select(
            func.date(Metric.fetched_at).label("date"),
            func.coalesce(func.sum(Metric.reach),       0).label("reach"),
            func.coalesce(func.sum(Metric.engagement),  0).label("engagement"),
            func.coalesce(func.sum(Metric.conversions), 0).label("conversions"),
        )
        .where(Metric.fetched_at >= since)
        .group_by(func.date(Metric.fetched_at))
        .order_by(func.date(Metric.fetched_at))
    )

    points = [
        TimelinePoint(
            date       = str(r.date),
            reach      = int(r.reach),
            engagement = int(r.engagement),
            conversions= int(r.conversions),
        )
        for r in rows.all()
    ]
    return TimelineResponse(points=points, days=days)


# ── GET /insights/by-platform ──────────────────────────────────────────────────

@router.get("/by-platform", response_model=list[PlatformRow], summary="Metrics grouped by platform")
async def get_by_platform(
    days: int        = Query(default=30, ge=1, le=365),
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
) -> list[PlatformRow]:
    since = _since(days)

    rows = await db.execute(
        select(
            Metric.platform,
            func.coalesce(func.sum(Metric.reach),       0).label("reach"),
            func.coalesce(func.sum(Metric.engagement),  0).label("engagement"),
            func.coalesce(func.sum(Metric.conversions), 0).label("conversions"),
            func.count(Metric.post_id.distinct()).label("posts"),
        )
        .where(Metric.fetched_at >= since)
        .group_by(Metric.platform)
        .order_by(func.sum(Metric.reach).desc())
    )

    return [
        PlatformRow(
            platform   = r.platform.value if hasattr(r.platform, "value") else str(r.platform),
            reach      = int(r.reach),
            engagement = int(r.engagement),
            conversions= int(r.conversions),
            posts      = int(r.posts),
        )
        for r in rows.all()
    ]


# ── GET /insights/by-campaign ─────────────────────────────────────────────────

@router.get("/by-campaign", response_model=list[CampaignRow], summary="Metrics grouped by campaign")
async def get_by_campaign(
    days: int        = Query(default=30, ge=1, le=365),
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
) -> list[CampaignRow]:
    since = _since(days)

    rows = await db.execute(
        select(
            Campaign.id.label("campaign_id"),
            Campaign.name.label("campaign_name"),
            func.coalesce(func.sum(Metric.reach),       0).label("reach"),
            func.coalesce(func.sum(Metric.engagement),  0).label("engagement"),
            func.coalesce(func.sum(Metric.conversions), 0).label("conversions"),
            func.count(Metric.post_id.distinct()).label("posts"),
        )
        .join(Post,     Post.id         == Metric.post_id)
        .join(Campaign, Campaign.id     == Post.campaign_id)
        .where(Metric.fetched_at >= since)
        .group_by(Campaign.id, Campaign.name)
        .order_by(func.sum(Metric.reach).desc())
        .limit(20)
    )

    return [
        CampaignRow(
            campaign_id  = str(r.campaign_id),
            campaign_name= r.campaign_name,
            reach        = int(r.reach),
            engagement   = int(r.engagement),
            conversions  = int(r.conversions),
            posts        = int(r.posts),
        )
        for r in rows.all()
    ]


# ── POST /insights/sync ────────────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse, summary="Sync metrics from Meta Graph API")
async def sync_insights(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
) -> SyncResponse:
    from backend.services.insights_sync import sync_published_posts
    synced = await sync_published_posts(db)
    return SyncResponse(
        synced  = synced,
        message = f"Synced {synced} post(s) from Meta. Metrics table updated.",
    )
