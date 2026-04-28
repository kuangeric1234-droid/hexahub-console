"""
Webhook routes — called BY external systems, not the frontend.
Auth: X-Webhook-Secret header (shared secret), not JWT.

POST /webhooks/publish-confirmation  XHS/WeChat manual post confirmed
POST /webhooks/platform-metric       analytics ingestion stub
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.config import settings
from backend.db.models import Post, PostStatus

log    = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_secret(x_webhook_secret: str = Header(...)) -> None:
    if x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(403, "Invalid webhook secret")


# ── POST /webhooks/publish-confirmation ───────────────────────────────────────

class PublishConfirmationRequest(BaseModel):
    post_id:           uuid.UUID
    platform:          str
    posted_at:         Optional[datetime] = None
    post_url:          Optional[str]      = None
    confirmation_note: Optional[str]      = None


class PublishConfirmationResponse(BaseModel):
    post_id: uuid.UUID
    status:  str
    message: str


@router.post("/publish-confirmation", response_model=PublishConfirmationResponse,
             summary="Confirm manual XHS / WeChat publish")
async def publish_confirmation(
    body: PublishConfirmationRequest,
    db:   AsyncSession = Depends(get_db),
    _:    None         = Depends(_verify_secret),
) -> PublishConfirmationResponse:
    post = await db.get(Post, body.post_id)
    if not post:
        raise HTTPException(404, f"Post {body.post_id} not found")

    post.status = PostStatus.published
    meta = dict(post.metadata_json or {})
    meta.update({
        "external_url":      body.post_url,
        "confirmation_note": body.confirmation_note,
        "confirmed_at":      (body.posted_at or datetime.now(timezone.utc)).isoformat(),
    })
    post.metadata_json = meta
    await db.flush()

    log.info("publish_confirmed", post_id=str(body.post_id), platform=body.platform,
             url=body.post_url)
    return PublishConfirmationResponse(
        post_id=body.post_id, status="published",
        message=f"Post {body.post_id} marked published on {body.platform}",
    )


# ── POST /webhooks/platform-metric (stub) ─────────────────────────────────────

class PlatformMetricRequest(BaseModel):
    post_id:     uuid.UUID
    platform:    str
    reach:       Optional[int]   = None
    engagement:  Optional[int]   = None
    ctr:         Optional[float] = None
    conversions: Optional[int]   = None
    fetched_at:  Optional[datetime] = None


@router.post("/platform-metric", response_model=dict, summary="Ingest platform metric (stub)")
async def platform_metric(
    body: PlatformMetricRequest,
    _:    None = Depends(_verify_secret),
) -> dict:
    log.info("metric_received", post_id=str(body.post_id), platform=body.platform)
    return {"received": True, "post_id": str(body.post_id)}
