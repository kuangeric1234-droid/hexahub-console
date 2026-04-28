"""
GET /approvals/queue — posts awaiting human review.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.db.models import ApprovalDecision, Campaign, Post

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalQueueItem(BaseModel):
    post_id:       uuid.UUID
    campaign_id:   uuid.UUID
    campaign_name: str
    platform:      str
    copy:          Optional[str]
    visual_url:    Optional[str]
    scheduled_at:  Optional[datetime]
    created_at:    Optional[datetime]


@router.get(
    "/queue",
    response_model=list[ApprovalQueueItem],
    summary="List posts awaiting approval",
)
async def get_approval_queue(
    skip:    int          = Query(default=0,  ge=0),
    limit:   int          = Query(default=50, ge=1, le=200),
    platform: Optional[str] = Query(default=None),
    db:      AsyncSession = Depends(get_db),
    _:       str          = Depends(get_current_user),
) -> list[ApprovalQueueItem]:
    """
    Returns all posts with approval_status='pending', oldest first.
    Includes campaign name so reviewers have context without a separate request.
    """
    q = (
        select(Post, Campaign.name.label("campaign_name"))
        .join(Campaign, Post.campaign_id == Campaign.id)
        .where(Post.approval_status == ApprovalDecision.pending)
        .order_by(Post.created_at.asc().nulls_last())
        .offset(skip)
        .limit(limit)
    )
    if platform:
        from backend.db.models import Platform
        try:
            q = q.where(Post.platform == Platform(platform))
        except ValueError:
            pass  # ignore unknown platform filter

    rows = (await db.execute(q)).all()

    return [
        ApprovalQueueItem(
            post_id=row.Post.id,
            campaign_id=row.Post.campaign_id,
            campaign_name=row.campaign_name,
            platform=row.Post.platform.value,
            copy=row.Post.copy,
            visual_url=row.Post.visual_url,
            scheduled_at=row.Post.scheduled_at,
            created_at=row.Post.created_at,
        )
        for row in rows
    ]
