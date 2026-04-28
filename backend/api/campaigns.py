"""
Campaign endpoints.

POST   /campaigns              create + kick off LangGraph workflow
GET    /campaigns              list (paginated)
GET    /campaigns/{id}         detail
GET    /campaigns/{id}/calendar  post slots grouped by date
GET    /campaigns/{id}/bilingual-view  EN/CN side-by-side for UI
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

import structlog

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.db.models import Campaign, CampaignStatus, Platform, Post
from backend.orchestrator.workflow import build_initial_state, get_workflow_app
from backend.services.campaign_service import get_bilingual_campaign_view

log    = structlog.get_logger()
router = APIRouter(prefix="/campaigns", tags=["campaigns"])

# ── Request / Response schemas ────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name:      str             = Field(min_length=2, max_length=255)
    brief:     str             = Field(min_length=20)
    objective: str             = Field(min_length=10)
    kpis:      dict[str, Any]  = Field(default_factory=dict)
    start_date: date
    end_date:   date
    platforms:  list[str]      = Field(min_length=1, description="e.g. ['linkedin','instagram']")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Q2 2026 Awareness",
            "brief": "Build awareness for Hexa Hub among cross-border e-commerce brands entering Australia.",
            "objective": "Generate 50 qualified space enquiries in 90 days",
            "kpis": {"enquiries": 50, "engagement_rate": 3.5},
            "start_date": "2026-04-01",
            "end_date": "2026-06-30",
            "platforms": ["linkedin", "instagram"],
        }
    })


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         uuid.UUID
    name:       str
    brief:      str
    objective:  str
    kpis:       dict[str, Any]
    start_date: date
    end_date:   date
    status:     str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class PostSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              uuid.UUID
    platform:        str
    pillar_id:       Optional[uuid.UUID]
    scheduled_at:    Optional[datetime]
    status:          str
    copy:            Optional[str]
    visual_url:      Optional[str]
    approval_status: str
    metadata_json:   dict[str, Any]


class CampaignCalendarResponse(BaseModel):
    campaign: CampaignResponse
    posts:    list[PostSlotResponse]
    total:    int


# ── Workflow background task ───────────────────────────────────────────────────

async def _start_campaign_workflow(
    campaign_id:    uuid.UUID,
    strategy_input: dict,
) -> None:
    """
    Runs the LangGraph campaign workflow in the background.

    The workflow runs to completion or pauses at approval_queue (interrupt).
    State is persisted in the module-level MemorySaver; resume via POST /posts/{id}/approve.
    """
    app    = get_workflow_app()
    config = {"configurable": {"thread_id": str(campaign_id)}}
    state  = build_initial_state(str(campaign_id), strategy_input)
    try:
        await app.ainvoke(state, config=config)
    except Exception as exc:
        log.error("campaign_workflow_failed", campaign_id=str(campaign_id), error=str(exc))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create campaign and start AI workflow",
)
async def create_campaign(
    body:             CampaignCreate,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    _:                str          = Depends(get_current_user),
) -> CampaignResponse:
    """
    Creates a Campaign record then asynchronously runs:
    StrategyAgent → CalendarAgent → (per post) CopyAgent → VisualAgent → ComplianceAgent → approval queue.

    The workflow pauses at each post's approval queue awaiting `POST /posts/{id}/approve`.
    """
    # Validate platforms
    valid_platforms = {p.value for p in Platform}
    invalid = [p for p in body.platforms if p not in valid_platforms]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown platform(s): {invalid}. Valid: {sorted(valid_platforms)}",
        )

    campaign = Campaign(
        name=body.name,
        brief=body.brief,
        objective=body.objective,
        kpis=body.kpis,
        start_date=body.start_date,
        end_date=body.end_date,
        status=CampaignStatus.active,
    )
    db.add(campaign)
    await db.flush()   # assigns campaign.id
    await db.commit()

    # Build StrategyInput dict for the workflow
    strategy_input = {
        "campaign_id": str(campaign.id),
        "name":        body.name,
        "brief":       body.brief,
        "objective":   body.objective,
        "kpis":        body.kpis,
        "start_date":  body.start_date.isoformat(),
        "end_date":    body.end_date.isoformat(),
        "platforms":   body.platforms,
    }

    background_tasks.add_task(_start_campaign_workflow, campaign.id, strategy_input)

    return CampaignResponse.model_validate(campaign)


@router.get("", response_model=list[CampaignResponse], summary="List campaigns")
async def list_campaigns(
    skip:   int         = Query(default=0,  ge=0),
    limit:  int         = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db:     AsyncSession = Depends(get_db),
    _:      str          = Depends(get_current_user),
) -> list[CampaignResponse]:
    q = select(Campaign).order_by(Campaign.created_at.desc()).offset(skip).limit(limit)
    if status_filter:
        try:
            q = q.where(Campaign.status == CampaignStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status_filter}")
    result = await db.execute(q)
    return [CampaignResponse.model_validate(c) for c in result.scalars().all()]


@router.get("/{campaign_id}", response_model=CampaignResponse, summary="Get campaign detail")
async def get_campaign(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           str          = Depends(get_current_user),
) -> CampaignResponse:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.get(
    "/{campaign_id}/calendar",
    response_model=CampaignCalendarResponse,
    summary="Get campaign post calendar",
)
async def get_campaign_calendar(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           str          = Depends(get_current_user),
) -> CampaignCalendarResponse:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result = await db.execute(
        select(Post)
        .where(Post.campaign_id == campaign_id)
        .order_by(Post.scheduled_at.asc().nulls_last())
    )
    posts = result.scalars().all()

    return CampaignCalendarResponse(
        campaign=CampaignResponse.model_validate(campaign),
        posts=[PostSlotResponse.model_validate(p) for p in posts],
        total=len(posts),
    )


@router.get(
    "/{campaign_id}/bilingual-view",
    summary="Bilingual EN/CN side-by-side campaign view",
)
async def bilingual_view(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           str          = Depends(get_current_user),
) -> dict:
    """
    Returns posts grouped by date with western (LinkedIn/Blog/IG) and
    chinese (XHS/WeChat) columns, ready for the side-by-side review UI.
    """
    return await get_bilingual_campaign_view(campaign_id, db)
