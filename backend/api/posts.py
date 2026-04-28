"""
Post endpoints.

GET    /posts/{id}          detail
PATCH  /posts/{id}          edit copy / scheduled_at before approval
POST   /posts/{id}/approve  approve (optionally resume workflow)
POST   /posts/{id}/reject   reject with required feedback
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.db.models import Approval, ApprovalDecision, Post, PostStatus

log    = structlog.get_logger()
router = APIRouter(prefix="/posts", tags=["posts"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              uuid.UUID
    campaign_id:     uuid.UUID
    platform:        str
    pillar_id:       Optional[uuid.UUID]
    scheduled_at:    Optional[datetime]
    status:          str
    copy:            Optional[str]
    visual_url:      Optional[str]
    approval_status: str


class PostUpdate(BaseModel):
    copy:         Optional[str]      = None
    visual_url:   Optional[str]      = None
    scheduled_at: Optional[datetime] = None


class ApproveRequest(BaseModel):
    feedback: Optional[str] = None


class RejectRequest(BaseModel):
    feedback: str   # required — rejection must explain why


# ── Workflow resume helper ────────────────────────────────────────────────────

async def _resume_workflow(campaign_id: uuid.UUID, decision: str, feedback: Optional[str]) -> None:
    """Resume the LangGraph workflow after an approval decision."""
    from langgraph.types import Command
    from backend.orchestrator.workflow import get_workflow_app

    app    = get_workflow_app()
    config = {"configurable": {"thread_id": str(campaign_id)}}
    try:
        await app.ainvoke(
            Command(resume={"decision": decision, "feedback": feedback}),
            config=config,
        )
    except Exception as exc:
        log.warning("workflow_resume_failed", campaign_id=str(campaign_id), error=str(exc))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{post_id}", response_model=PostResponse, summary="Get post detail")
async def get_post(
    post_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    _:       str          = Depends(get_current_user),
) -> PostResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostResponse.model_validate(post)


@router.patch("/{post_id}", response_model=PostResponse, summary="Edit post before approval")
async def update_post(
    post_id: uuid.UUID,
    body:    PostUpdate,
    db:      AsyncSession = Depends(get_db),
    _:       str          = Depends(get_current_user),
) -> PostResponse:
    """Update copy, visual_url, or scheduled_at. Only allowed while post is pending approval."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.approval_status == ApprovalDecision.approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot edit an approved post",
        )

    if body.copy         is not None: post.copy         = body.copy
    if body.visual_url   is not None: post.visual_url   = body.visual_url
    if body.scheduled_at is not None: post.scheduled_at = body.scheduled_at

    await db.flush()
    return PostResponse.model_validate(post)


@router.post(
    "/{post_id}/approve",
    response_model=PostResponse,
    summary="Approve a post and trigger publishing",
)
async def approve_post(
    post_id:          uuid.UUID,
    body:             ApproveRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    _:                str          = Depends(get_current_user),
) -> PostResponse:
    """
    Mark the post as approved, create an Approval record, and resume the
    LangGraph workflow so PublishingAgent can dispatch it.
    """
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.approval_status != ApprovalDecision.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Post approval_status is '{post.approval_status.value}', expected 'pending'",
        )

    post.approval_status = ApprovalDecision.approved
    post.status          = PostStatus.approved

    approval = Approval(
        post_id=post_id,
        reviewer=_,   # username from JWT
        decision=ApprovalDecision.approved,
        feedback=body.feedback,
    )
    db.add(approval)
    await db.flush()

    # Resume the LangGraph workflow in background
    background_tasks.add_task(_resume_workflow, post.campaign_id, "approved", body.feedback)

    log.info("post_approved", post_id=str(post_id), reviewer=_)
    return PostResponse.model_validate(post)


@router.post(
    "/{post_id}/reject",
    response_model=PostResponse,
    summary="Reject a post with feedback",
)
async def reject_post(
    post_id:          uuid.UUID,
    body:             RejectRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    _:                str          = Depends(get_current_user),
) -> PostResponse:
    """
    Mark the post as rejected. The LangGraph workflow is resumed with
    'rejected' so it moves on to the next post (skips publishing for this one).
    """
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.approval_status != ApprovalDecision.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Post approval_status is '{post.approval_status.value}', expected 'pending'",
        )

    post.approval_status = ApprovalDecision.rejected
    post.status          = PostStatus.rejected

    approval = Approval(
        post_id=post_id,
        reviewer=_,
        decision=ApprovalDecision.rejected,
        feedback=body.feedback,
    )
    db.add(approval)
    await db.flush()

    background_tasks.add_task(_resume_workflow, post.campaign_id, "rejected", body.feedback)

    log.info("post_rejected", post_id=str(post_id), reviewer=_)
    return PostResponse.model_validate(post)
