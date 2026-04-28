"""
Approval routes.

GET  /approvals/queue           posts pending human review
GET  /approvals/queue/count     badge count
GET  /approvals/history         past decisions
POST /approvals/batch-approve   bulk approve
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.api.schemas.approval import (
    ApprovalHistoryItem,
    ApprovalQueueCount,
    ApprovalQueueItem,
    BatchApproveRequest,
    BatchApproveResult,
)
from backend.db.models import Approval, ApprovalDecision, Campaign, Post, PostStatus, User

log    = structlog.get_logger()
router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/queue", response_model=list[ApprovalQueueItem], summary="Posts pending approval")
async def get_queue(
    page:     int          = Query(default=1, ge=1),
    page_size:int          = Query(default=50, ge=1, le=200),
    platform: Optional[str] = Query(default=None),
    db:       AsyncSession = Depends(get_db),
    _:        User         = Depends(get_current_user),
) -> list[ApprovalQueueItem]:
    from backend.db.models import Platform as PlatformEnum
    q = (
        select(Post, Campaign.name.label("campaign_name"))
        .join(Campaign, Post.campaign_id == Campaign.id)
        .where(Post.approval_status == ApprovalDecision.pending)
        .order_by(Post.created_at.asc().nulls_last())
        .offset((page - 1) * page_size).limit(page_size)
    )
    if platform:
        try:    q = q.where(Post.platform == PlatformEnum(platform))
        except ValueError: pass

    rows = (await db.execute(q)).all()
    return [
        ApprovalQueueItem(
            post_id=row.Post.id, campaign_id=row.Post.campaign_id,
            campaign_name=row.campaign_name, platform=row.Post.platform.value,
            copy=row.Post.copy, visual_url=row.Post.visual_url,
            scheduled_at=row.Post.scheduled_at, created_at=row.Post.created_at,
        )
        for row in rows
    ]


@router.get("/queue/count", response_model=ApprovalQueueCount, summary="Count pending approvals")
async def queue_count(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
) -> ApprovalQueueCount:
    result = await db.execute(
        select(func.count()).select_from(Post)
        .where(Post.approval_status == ApprovalDecision.pending)
    )
    return ApprovalQueueCount(count=result.scalar_one())


@router.get("/history", response_model=list[ApprovalHistoryItem], summary="Approval history")
async def approval_history(
    reviewer:   Optional[str]       = Query(default=None),
    decision:   Optional[str]       = Query(default=None),
    campaign_id:Optional[uuid.UUID] = Query(default=None),
    page:       int                  = Query(default=1, ge=1),
    page_size:  int                  = Query(default=50, ge=1, le=200),
    db:         AsyncSession         = Depends(get_db),
    _:          User                 = Depends(get_current_user),
) -> list[ApprovalHistoryItem]:
    q = select(Approval).order_by(Approval.timestamp.desc()) \
        .offset((page - 1) * page_size).limit(page_size)
    if reviewer:
        q = q.where(Approval.reviewer == reviewer)
    if decision:
        try:    q = q.where(Approval.decision == ApprovalDecision(decision))
        except ValueError: pass
    if campaign_id:
        q = q.join(Post, Approval.post_id == Post.id).where(Post.campaign_id == campaign_id)
    result = await db.execute(q)
    return [ApprovalHistoryItem.model_validate(a) for a in result.scalars().all()]


@router.post("/batch-approve", response_model=BatchApproveResult, summary="Bulk approve posts")
async def batch_approve(
    body:         BatchApproveRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> BatchApproveResult:
    from backend.orchestrator.workflow import get_workflow_app
    from langgraph.types import Command

    approved: list[uuid.UUID] = []
    failed:   list[dict]      = []

    for post_id in body.post_ids:
        try:
            post = await db.get(Post, post_id)
            if not post:
                failed.append({"post_id": str(post_id), "reason": "not found"})
                continue
            if post.approval_status != ApprovalDecision.pending:
                failed.append({"post_id": str(post_id), "reason": "not pending"})
                continue

            post.approval_status = ApprovalDecision.approved
            post.status          = PostStatus.approved
            db.add(Approval(
                post_id=post_id, reviewer=current_user.email,
                decision=ApprovalDecision.approved, feedback=body.feedback,
            ))
            await db.flush()
            approved.append(post_id)

            # resume workflow non-blocking
            try:
                app    = get_workflow_app()
                config = {"configurable": {"thread_id": str(post.campaign_id)}}
                await app.ainvoke(
                    Command(resume={"decision": "approved", "feedback": body.feedback}),
                    config=config,
                )
            except Exception as exc:
                log.warning("batch_resume_failed", post_id=str(post_id), error=str(exc))

        except Exception as exc:
            await db.rollback()
            failed.append({"post_id": str(post_id), "reason": str(exc)})

    log.info("batch_approve", approved=len(approved), failed=len(failed), by=current_user.email)
    return BatchApproveResult(approved=approved, failed=failed)
