"""
Campaign routes.

POST   /campaigns/draft                   AI-generate a campaign brief from a one-liner
POST   /campaigns                         create + kick off workflow
GET    /campaigns                         list (paginated, filterable)
GET    /campaigns/{id}                    detail
PATCH  /campaigns/{id}                    update name/dates/status
DELETE /campaigns/{id}                    soft-delete (status=archived)
GET    /campaigns/{id}/calendar           post slots
POST   /campaigns/{id}/regenerate-calendar  re-run CalendarAgent
POST   /campaigns/{id}/run-workflow       manually re-trigger stalled workflow
GET    /campaigns/{id}/bilingual-view     EN/CN side-by-side
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.config import settings
from backend.api.schemas.campaign import (
    CampaignCalendarResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
    PostSlotResponse,
)
from backend.db.models import Campaign, CampaignStatus, Platform, Post, User
from backend.orchestrator.workflow import build_initial_state, get_workflow_app
from backend.services.campaign_service import get_bilingual_campaign_view

log    = structlog.get_logger()
router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ── background helpers ────────────────────────────────────────────────────────

async def _start_workflow(campaign_id: uuid.UUID, strategy_input: dict) -> None:
    app    = get_workflow_app()
    config = {"configurable": {"thread_id": str(campaign_id)}}
    state  = build_initial_state(str(campaign_id), strategy_input)
    try:
        await app.ainvoke(state, config=config)
    except Exception as exc:
        log.error("campaign_workflow_failed", campaign_id=str(campaign_id), error=str(exc))


# ── POST /campaigns/draft ─────────────────────────────────────────────────────

class CampaignDraftRequest(BaseModel):
    prompt:   str       = Field(min_length=10, max_length=500,
                                description="One or two sentences describing the campaign")
    weeks:    int       = Field(default=8, ge=2, le=26)
    language: str       = Field(default="en")


class CampaignDraftResponse(BaseModel):
    name:                str
    brief:               str
    objective:           str
    kpis:                dict[str, Any]
    suggested_platforms: list[str]
    suggested_weeks:     int
    ai_generated:        bool   # False when falling back to template


def _template_draft(prompt: str, weeks: int) -> CampaignDraftResponse:
    """Structured fallback when no LLM is available."""
    today      = date.today()
    start      = today + timedelta(days=7)
    name_words = prompt.split()[:6]
    name       = " ".join(w.capitalize() for w in name_words)

    return CampaignDraftResponse(
        name=name,
        brief=(
            f"{prompt.strip().rstrip('.')}. "
            "This campaign will build brand awareness, drive engagement across our target platforms, "
            "and generate qualified leads through a mix of educational and promotional content. "
            "The content strategy will align with our brand pillars of People, Place, Culture and Legacy, "
            "reflecting the Creator brand archetype through authentic storytelling and collaborative narratives."
        ),
        objective=(
            "Generate qualified enquiries and increase brand awareness among our primary target audience "
            "through consistent, platform-native content that reinforces our positioning and values."
        ),
        kpis={
            "enquiries":       20,
            "engagement_rate": 3.5,
            "follower_growth": 200,
            "reach":           10000,
        },
        suggested_platforms=["linkedin", "instagram"],
        suggested_weeks=weeks,
        ai_generated=False,
    )


async def _ai_draft(prompt: str, weeks: int) -> CampaignDraftResponse:
    """LLM-powered campaign brief generation."""
    from backend.llm.client import LLMClient, LLMProvider
    from backend.utils.json_utils import extract_json

    client = LLMClient(provider=LLMProvider.ANTHROPIC)
    system = (
        "You are a senior marketing strategist. Generate a structured campaign brief in JSON. "
        "Return ONLY valid JSON with these exact keys: "
        "name (string, 3-6 words), brief (string, 60-120 words, professional tone), "
        "objective (string, 20-40 words, measurable), "
        "kpis (object with keys: enquiries, engagement_rate, follower_growth, reach — all numbers), "
        "suggested_platforms (array, choose from: linkedin, instagram, blog, xiaohongshu, wechat_moments), "
        "suggested_weeks (integer)."
    )
    user = f"Campaign prompt: {prompt}\nCampaign duration: {weeks} weeks\nReturn JSON only."

    response = await client.complete(
        system_prompt=system,
        user_prompt=user,
        max_tokens=800,
        temperature=0.7,
    )
    raw  = extract_json(response.content)
    return CampaignDraftResponse(**raw, ai_generated=True)


@router.post("/draft", response_model=CampaignDraftResponse,
             summary="AI-generate a campaign brief from a one-liner")
async def draft_campaign(
    body: CampaignDraftRequest,
    _:    User = Depends(get_current_user),
) -> CampaignDraftResponse:
    """
    Takes a short plain-English prompt and returns a fully-formed campaign brief.
    Uses the LLM if ANTHROPIC_API_KEY is configured, otherwise returns a structured template.
    The result is editable before the user confirms campaign creation.
    """
    if settings.ANTHROPIC_API_KEY:
        try:
            return await _ai_draft(body.prompt, body.weeks)
        except Exception as exc:
            log.warning("ai_draft_failed", error=str(exc))
    return _template_draft(body.prompt, body.weeks)


# ── POST /campaigns ────────────────────────────────────────────────────────────

@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED,
             summary="Create campaign and start AI workflow")
async def create_campaign(
    body:             CampaignCreate,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    current_user:     User         = Depends(get_current_user),
) -> CampaignResponse:
    valid_platforms = {p.value for p in Platform}
    invalid = [p for p in body.platforms if p not in valid_platforms]
    if invalid:
        raise HTTPException(422, f"Unknown platforms: {invalid}. Valid: {sorted(valid_platforms)}")

    campaign = Campaign(
        name=body.name, brief=body.brief, objective=body.objective,
        kpis=body.kpis, start_date=body.start_date, end_date=body.end_date,
        status=CampaignStatus.active,
    )
    db.add(campaign)
    await db.flush()
    await db.commit()

    strategy_input = {
        "campaign_id": str(campaign.id), "name": body.name,
        "brief": body.brief, "objective": body.objective, "kpis": body.kpis,
        "start_date": body.start_date.isoformat(), "end_date": body.end_date.isoformat(),
        "platforms": body.platforms,
    }
    background_tasks.add_task(_start_workflow, campaign.id, strategy_input)
    log.info("campaign_created", campaign_id=str(campaign.id), by=current_user.email)
    return CampaignResponse.model_validate(campaign)


# ── GET /campaigns ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[CampaignResponse], summary="List campaigns")
async def list_campaigns(
    page:      int          = Query(default=1, ge=1),
    page_size: int          = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db:        AsyncSession = Depends(get_db),
    _:         User         = Depends(get_current_user),
) -> list[CampaignResponse]:
    skip = (page - 1) * page_size
    q = select(Campaign).order_by(Campaign.created_at.desc()).offset(skip).limit(page_size)
    if status_filter:
        try:
            q = q.where(Campaign.status == CampaignStatus(status_filter))
        except ValueError:
            raise HTTPException(422, f"Invalid status: {status_filter}")
    result = await db.execute(q)
    return [CampaignResponse.model_validate(c) for c in result.scalars().all()]


# ── GET /campaigns/{id} ────────────────────────────────────────────────────────

@router.get("/{campaign_id}", response_model=CampaignResponse, summary="Campaign detail")
async def get_campaign(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           User         = Depends(get_current_user),
) -> CampaignResponse:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, f"Campaign {campaign_id} not found")
    return CampaignResponse.model_validate(campaign)


# ── PATCH /campaigns/{id} ─────────────────────────────────────────────────────

@router.patch("/{campaign_id}", response_model=CampaignResponse, summary="Update campaign")
async def update_campaign(
    campaign_id: uuid.UUID,
    body:        CampaignUpdate,
    db:          AsyncSession = Depends(get_db),
    _:           User         = Depends(get_current_user),
) -> CampaignResponse:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, f"Campaign {campaign_id} not found")
    if body.name       is not None: campaign.name       = body.name
    if body.start_date is not None: campaign.start_date = body.start_date
    if body.end_date   is not None: campaign.end_date   = body.end_date
    if body.kpis       is not None: campaign.kpis       = body.kpis
    if body.status     is not None:
        try:
            campaign.status = CampaignStatus(body.status)
        except ValueError:
            raise HTTPException(422, f"Invalid status: {body.status}")
    await db.flush()
    return CampaignResponse.model_validate(campaign)


# ── POST /campaigns/{id}/archive — soft delete ────────────────────────────────

@router.post("/{campaign_id}/archive", status_code=status.HTTP_204_NO_CONTENT,
             response_model=None, summary="Archive campaign (soft delete)")
async def archive_campaign(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           User         = Depends(get_current_user),
) -> None:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, f"Campaign {campaign_id} not found")
    campaign.status = CampaignStatus.archived
    await db.flush()


# ── DELETE /campaigns/{id} — hard delete ──────────────────────────────────────

@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_model=None, summary="Permanently delete campaign and all posts")
async def delete_campaign(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           User         = Depends(get_current_user),
) -> None:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, f"Campaign {campaign_id} not found")
    await db.delete(campaign)
    await db.flush()


# ── GET /campaigns/{id}/calendar ──────────────────────────────────────────────

@router.get("/{campaign_id}/calendar", response_model=CampaignCalendarResponse,
            summary="Campaign post calendar")
async def get_calendar(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           User         = Depends(get_current_user),
) -> CampaignCalendarResponse:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, f"Campaign {campaign_id} not found")
    result = await db.execute(
        select(Post).where(Post.campaign_id == campaign_id)
        .order_by(Post.scheduled_at.asc().nulls_last())
    )
    posts = result.scalars().all()
    return CampaignCalendarResponse(
        campaign=CampaignResponse.model_validate(campaign),
        posts=[PostSlotResponse.model_validate(p) for p in posts],
        total=len(posts),
    )


# ── POST /campaigns/{id}/regenerate-calendar ──────────────────────────────────

@router.post("/{campaign_id}/regenerate-calendar", response_model=dict,
             summary="Re-run CalendarAgent for this campaign")
async def regenerate_calendar(
    campaign_id:      uuid.UUID,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    current_user:     User         = Depends(get_current_user),
) -> dict:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    strategy_input = {
        "campaign_id": str(campaign_id), "name": campaign.name,
        "brief": campaign.brief, "objective": campaign.objective, "kpis": campaign.kpis,
        "start_date": campaign.start_date.isoformat(), "end_date": campaign.end_date.isoformat(),
        "platforms": [],
    }
    background_tasks.add_task(_start_workflow, campaign_id, strategy_input)
    return {"message": "Calendar regeneration queued", "campaign_id": str(campaign_id)}


# ── POST /campaigns/{id}/run-workflow ─────────────────────────────────────────

@router.post("/{campaign_id}/run-workflow", response_model=dict,
             summary="Manually re-trigger stalled workflow")
async def run_workflow(
    campaign_id:      uuid.UUID,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    current_user:     User         = Depends(get_current_user),
) -> dict:
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, f"Campaign {campaign_id} not found")

    strategy_input = {
        "campaign_id": str(campaign_id), "name": campaign.name,
        "brief": campaign.brief, "objective": campaign.objective, "kpis": campaign.kpis,
        "start_date": campaign.start_date.isoformat(), "end_date": campaign.end_date.isoformat(),
        "platforms": [],
    }
    background_tasks.add_task(_start_workflow, campaign_id, strategy_input)
    log.info("workflow_manual_trigger", campaign_id=str(campaign_id), by=current_user.email)
    return {"message": "Workflow triggered", "campaign_id": str(campaign_id)}


# ── POST /campaigns/{id}/pause ────────────────────────────────────────────────

@router.post("/{campaign_id}/pause", response_model=dict, summary="Pause workflow generation")
async def pause_workflow(
    campaign_id: uuid.UUID,
    _:           User = Depends(get_current_user),
) -> dict:
    from backend.orchestrator.control import pause
    pause(str(campaign_id))
    log.info("workflow_paused", campaign_id=str(campaign_id))
    return {"message": "paused", "campaign_id": str(campaign_id)}


# ── POST /campaigns/{id}/resume ───────────────────────────────────────────────

@router.post("/{campaign_id}/resume", response_model=dict, summary="Resume workflow generation")
async def resume_workflow(
    campaign_id: uuid.UUID,
    _:           User = Depends(get_current_user),
) -> dict:
    from backend.orchestrator.control import resume
    resume(str(campaign_id))
    log.info("workflow_resumed", campaign_id=str(campaign_id))
    return {"message": "resumed", "campaign_id": str(campaign_id)}


# ── GET /campaigns/{id}/bilingual-view ────────────────────────────────────────

@router.get("/{campaign_id}/bilingual-view", summary="EN/CN side-by-side view")
async def bilingual_view(
    campaign_id: uuid.UUID,
    db:          AsyncSession = Depends(get_db),
    _:           User         = Depends(get_current_user),
) -> dict:
    return await get_bilingual_campaign_view(campaign_id, db)
