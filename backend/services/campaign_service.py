"""
CampaignService — query helpers used by the API layer.

get_bilingual_campaign_view
    Powers the side-by-side EN/CN review UI. Groups posts by date and
    separates them into western (LinkedIn, Blog, Instagram) and chinese
    (Xiaohongshu, WeChat Moments) columns.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Campaign, Platform, Post

_WESTERN_PLATFORMS = {Platform.linkedin, Platform.blog, Platform.instagram}
_CHINESE_PLATFORMS = {Platform.xiaohongshu, Platform.wechat_moments}


async def get_bilingual_campaign_view(
    campaign_id: UUID,
    db:          AsyncSession,
) -> dict:
    """
    Return campaign posts grouped by scheduled date, split into western and
    chinese columns for side-by-side review.

    Output shape
    ------------
    {
        "campaign": {
            "id":         "uuid",
            "name":       "...",
            "status":     "active",
            "start_date": "2026-04-01",
            "end_date":   "2026-06-30",
        },
        "rows": [
            {
                "date": "2026-04-06",
                "western": [
                    {"platform": "linkedin", "post_id": "uuid", "copy": "...",
                     "status": "approved", "scheduled_at": "2026-04-06T09:00:00+00:00"}
                ],
                "chinese": [
                    {"platform": "xiaohongshu", "post_id": "uuid", "copy": "...",
                     "status": "pending", "scheduled_at": "2026-04-06T09:00:00+00:00"}
                ]
            },
            ...
        ]
    }

    Posts without scheduled_at are grouped under "unscheduled".
    """
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        return {"campaign": None, "rows": []}

    result = await db.execute(
        select(Post)
        .where(Post.campaign_id == campaign_id)
        .order_by(Post.scheduled_at.asc().nulls_last())
    )
    posts = result.scalars().all()

    rows_by_date: dict[str, dict] = {}

    for post in posts:
        date_key = (
            post.scheduled_at.date().isoformat()
            if post.scheduled_at
            else "unscheduled"
        )

        if date_key not in rows_by_date:
            rows_by_date[date_key] = {
                "date":    date_key,
                "western": [],
                "chinese": [],
            }

        post_data = {
            "platform":     post.platform.value,
            "post_id":      str(post.id),
            "copy":         post.copy or "",
            "status":       post.approval_status.value,
            "post_status":  post.status.value,
            "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        }

        if post.platform in _WESTERN_PLATFORMS:
            rows_by_date[date_key]["western"].append(post_data)
        elif post.platform in _CHINESE_PLATFORMS:
            rows_by_date[date_key]["chinese"].append(post_data)
        # Posts on unknown platforms are silently excluded from the view

    # Sort rows chronologically; "unscheduled" always last
    sorted_rows = sorted(
        rows_by_date.values(),
        key=lambda r: ("~" if r["date"] == "unscheduled" else r["date"]),
    )

    return {
        "campaign": {
            "id":         str(campaign.id),
            "name":       campaign.name,
            "brief":      campaign.brief,
            "objective":  campaign.objective,
            "status":     campaign.status.value,
            "start_date": campaign.start_date.isoformat(),
            "end_date":   campaign.end_date.isoformat(),
        },
        "rows": sorted_rows,
    }


async def get_campaign_summary(
    campaign_id: UUID,
    db:          AsyncSession,
) -> dict:
    """
    Lightweight summary: post counts by platform and approval status.
    Used by the campaign list view.
    """
    campaign = await db.get(Campaign, campaign_id)
    if not campaign:
        return {}

    result = await db.execute(
        select(Post).where(Post.campaign_id == campaign_id)
    )
    posts = result.scalars().all()

    by_platform: dict[str, int] = {}
    by_status:   dict[str, int] = {}

    for post in posts:
        by_platform[post.platform.value] = by_platform.get(post.platform.value, 0) + 1
        by_status[post.approval_status.value] = by_status.get(post.approval_status.value, 0) + 1

    return {
        "campaign_id":  str(campaign.id),
        "name":         campaign.name,
        "status":       campaign.status.value,
        "total_posts":  len(posts),
        "by_platform":  by_platform,
        "by_approval":  by_status,
    }
