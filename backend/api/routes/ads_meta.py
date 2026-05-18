"""
Meta Ads routes.

POST   /ads/meta/campaigns              create full campaign (campaign + adset, always PAUSED)
GET    /ads/meta/campaigns              list all ad campaigns
GET    /ads/meta/campaigns/{id}/insights  performance metrics from Meta
POST   /ads/meta/campaigns/{id}/pause   pause campaign on Meta
POST   /ads/meta/campaigns/{id}/resume  resume campaign on Meta
POST   /ads/meta/campaigns/{id}/sync    pull latest insights into metrics table
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.db.models import AdCampaign, User
from backend.services.meta_ads import MetaAdsService

log    = structlog.get_logger()
router = APIRouter(prefix="/ads/meta", tags=["ads"])


# ── Request / Response models ──────────────────────────────────────────────────

class CreateAdCampaignRequest(BaseModel):
    name:                str   = Field(min_length=2, max_length=255)
    daily_budget_aud:    float = Field(gt=0, description="Daily budget in AUD dollars (e.g. 50.0)")
    targeting_location:  str   = Field(default="AU", description="ISO country code(s), comma-separated")
    targeting_interests: str   = Field(default="",   description="Comma-separated interest keywords (stored as summary)")
    campaign_id:         Optional[uuid.UUID] = Field(default=None, description="Link to a Hexa Hub content campaign")


class AdCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:               uuid.UUID
    campaign_id:      Optional[uuid.UUID]
    meta_campaign_id: str
    meta_adset_id:    Optional[str]
    meta_ad_id:       Optional[str]
    status:           str
    daily_budget:     Optional[int]   # AUD cents stored in DB
    daily_budget_aud: Optional[float] # dollars, computed
    objective:        Optional[str]
    targeting_summary:Optional[str]
    synced_at:        Optional[datetime]
    created_at:       Optional[datetime]
    updated_at:       Optional[datetime]


class InsightsResponse(BaseModel):
    meta_campaign_id: str
    reach:            int
    impressions:      int
    clicks:           int
    ctr:              float
    spend_aud:        float
    leads:            int
    cpl_aud:          float


def _to_response(ad: AdCampaign) -> AdCampaignResponse:
    return AdCampaignResponse(
        id               = ad.id,
        campaign_id      = ad.campaign_id,
        meta_campaign_id = ad.meta_campaign_id,
        meta_adset_id    = ad.meta_adset_id,
        meta_ad_id       = ad.meta_ad_id,
        status           = ad.status,
        daily_budget     = ad.daily_budget,
        daily_budget_aud = round(ad.daily_budget / 100, 2) if ad.daily_budget else None,
        objective        = ad.objective,
        targeting_summary= ad.targeting_summary,
        synced_at        = ad.synced_at,
        created_at       = ad.created_at,
        updated_at       = ad.updated_at,
    )


# ── POST /ads/meta/campaigns ───────────────────────────────────────────────────

@router.post("/campaigns", response_model=AdCampaignResponse, status_code=201,
             summary="Create a Meta Ads lead gen campaign (always PAUSED)")
async def create_ad_campaign(
    body: CreateAdCampaignRequest,
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
) -> AdCampaignResponse:
    try:
        svc = await MetaAdsService.from_db(db)
    except ValueError as exc:
        raise HTTPException(503, str(exc))

    try:
        # Step 1 — create campaign on Meta (always PAUSED)
        campaign_result = await svc.create_campaign(
            name      = body.name,
            objective = "OUTCOME_LEADS",
        )

        # Step 2 — create ad set
        adset_result = await svc.create_adset(
            name                = f"{body.name} — Ad Set",
            meta_campaign_id    = campaign_result.meta_campaign_id,
            daily_budget_aud    = body.daily_budget_aud,
            targeting_location  = body.targeting_location,
            targeting_interests = body.targeting_interests,
        )

    except RuntimeError as exc:
        log.error("meta_create_campaign_failed", error=str(exc))
        raise HTTPException(502, f"Meta API error: {exc}")

    targeting_summary = (
        f"Location: {body.targeting_location}"
        + (f" | Interests: {body.targeting_interests}" if body.targeting_interests else "")
    )

    ad_row = AdCampaign(
        campaign_id      = body.campaign_id,
        meta_campaign_id = campaign_result.meta_campaign_id,
        meta_adset_id    = adset_result.meta_adset_id,
        status           = "PAUSED",
        daily_budget     = int(body.daily_budget_aud * 100),
        objective        = "OUTCOME_LEADS",
        targeting_summary= targeting_summary,
        created_at       = datetime.now(timezone.utc),
        updated_at       = datetime.now(timezone.utc),
    )
    db.add(ad_row)
    await db.flush()

    log.info(
        "ad_campaign_created",
        id=str(ad_row.id),
        meta_campaign_id=campaign_result.meta_campaign_id,
        meta_adset_id=adset_result.meta_adset_id,
    )
    return _to_response(ad_row)


# ── GET /ads/meta/campaigns ────────────────────────────────────────────────────

@router.get("/campaigns", response_model=list[AdCampaignResponse],
            summary="List all Meta Ads campaigns")
async def list_ad_campaigns(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
) -> list[AdCampaignResponse]:
    result = await db.execute(
        select(AdCampaign).order_by(AdCampaign.created_at.desc())
    )
    return [_to_response(ad) for ad in result.scalars().all()]


# ── GET /ads/meta/campaigns/{id}/insights ─────────────────────────────────────

@router.get("/campaigns/{ad_campaign_id}/insights", response_model=InsightsResponse,
            summary="Fetch live performance metrics from Meta Insights API")
async def get_campaign_insights(
    ad_campaign_id: uuid.UUID,
    date_preset:    str = "last_30d",
    db:             AsyncSession = Depends(get_db),
    _:              User         = Depends(get_current_user),
) -> InsightsResponse:
    ad = await db.get(AdCampaign, ad_campaign_id)
    if not ad:
        raise HTTPException(404, "Ad campaign not found")

    try:
        svc = await MetaAdsService.from_db(db)
    except ValueError as exc:
        raise HTTPException(503, str(exc))

    try:
        insights = await svc.get_insights(ad.meta_campaign_id, date_preset=date_preset)
    except RuntimeError as exc:
        raise HTTPException(502, f"Meta API error: {exc}")

    return InsightsResponse(
        meta_campaign_id = insights.meta_campaign_id,
        reach            = insights.reach,
        impressions      = insights.impressions,
        clicks           = insights.clicks,
        ctr              = insights.ctr,
        spend_aud        = insights.spend_aud,
        leads            = insights.leads,
        cpl_aud          = insights.cpl_aud,
    )


# ── POST /ads/meta/campaigns/{id}/pause ───────────────────────────────────────

@router.post("/campaigns/{ad_campaign_id}/pause", response_model=AdCampaignResponse,
             summary="Pause a Meta Ads campaign")
async def pause_ad_campaign(
    ad_campaign_id: uuid.UUID,
    db:             AsyncSession = Depends(get_db),
    _:              User         = Depends(get_current_user),
) -> AdCampaignResponse:
    ad = await db.get(AdCampaign, ad_campaign_id)
    if not ad:
        raise HTTPException(404, "Ad campaign not found")

    try:
        svc = await MetaAdsService.from_db(db)
        await svc.pause_campaign(ad.meta_campaign_id)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, f"Meta API error: {exc}")

    ad.status     = "PAUSED"
    ad.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _to_response(ad)


# ── POST /ads/meta/campaigns/{id}/resume ──────────────────────────────────────

@router.post("/campaigns/{ad_campaign_id}/resume", response_model=AdCampaignResponse,
             summary="Resume (activate) a Meta Ads campaign")
async def resume_ad_campaign(
    ad_campaign_id: uuid.UUID,
    db:             AsyncSession = Depends(get_db),
    _:              User         = Depends(get_current_user),
) -> AdCampaignResponse:
    ad = await db.get(AdCampaign, ad_campaign_id)
    if not ad:
        raise HTTPException(404, "Ad campaign not found")

    try:
        svc = await MetaAdsService.from_db(db)
        await svc.resume_campaign(ad.meta_campaign_id)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, f"Meta API error: {exc}")

    ad.status     = "ACTIVE"
    ad.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _to_response(ad)


# ── POST /ads/meta/campaigns/{id}/sync ────────────────────────────────────────

@router.post("/campaigns/{ad_campaign_id}/sync", response_model=AdCampaignResponse,
             summary="Sync latest Meta Insights into the metrics table")
async def sync_ad_campaign(
    ad_campaign_id: uuid.UUID,
    db:             AsyncSession = Depends(get_db),
    _:              User         = Depends(get_current_user),
) -> AdCampaignResponse:
    ad = await db.get(AdCampaign, ad_campaign_id)
    if not ad:
        raise HTTPException(404, "Ad campaign not found")

    try:
        svc      = await MetaAdsService.from_db(db)
        insights = await svc.get_insights(ad.meta_campaign_id)
    except ValueError as exc:
        raise HTTPException(503, str(exc))
    except RuntimeError as exc:
        raise HTTPException(502, f"Meta API error: {exc}")

    from backend.db.models import Metric, Platform, Post
    from sqlalchemy import select as _sel

    if ad.campaign_id:
        post_q = await db.execute(
            _sel(Post).where(Post.campaign_id == ad.campaign_id).limit(1)
        )
        post = post_q.scalar_one_or_none()
        if post:
            metric = Metric(
                post_id    = post.id,
                platform   = Platform.facebook,
                reach      = insights.reach,
                engagement = insights.clicks,
                ctr        = insights.ctr,
                conversions= insights.leads,
                fetched_at = datetime.now(timezone.utc),
            )
            db.add(metric)

    ad.synced_at  = datetime.now(timezone.utc)
    ad.updated_at = datetime.now(timezone.utc)
    await db.flush()

    log.info("ad_campaign_synced", id=str(ad_campaign_id), leads=insights.leads)
    return _to_response(ad)
