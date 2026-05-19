"""
Insights sync — pulls post-level metrics from the Meta Graph API
and writes them into the metrics table.

Supports:
  Instagram media:  GET /{media-id}/insights
  Facebook posts:   GET /{post-id}/insights

Called by:
  - POST /insights/sync  (on-demand)
  - APScheduler daily job (06:30 UTC, after the Meta Ads sync)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Metric, Platform, Post, PostStatus, SocialConnection

log = structlog.get_logger()

_GRAPH = "https://graph.facebook.com/v21.0"

_IG_METRICS  = "reach,impressions,likes,comments,shares,saved"
_FB_METRICS  = "post_impressions,post_impressions_unique,post_engaged_users,post_clicks"


async def _get_token(db: AsyncSession) -> Optional[str]:
    """Load page_access_token from social_connections."""
    result = await db.execute(
        select(SocialConnection).where(SocialConnection.provider == "meta")
    )
    conn = result.scalars().first()
    if conn and conn.page_access_token:
        return conn.page_access_token
    from backend.config import settings
    return settings.META_ACCESS_TOKEN or None


async def _fetch_ig_insights(
    media_id: str,
    access_token: str,
    client: httpx.AsyncClient,
) -> dict:
    resp = await client.get(f"{_GRAPH}/{media_id}/insights", params={
        "metric":       _IG_METRICS,
        "access_token": access_token,
    })
    if resp.status_code != 200:
        log.warning("ig_insights_failed", media_id=media_id, status=resp.status_code)
        return {}
    data = {}
    for item in resp.json().get("data", []):
        data[item["name"]] = item.get("values", [{}])[0].get("value", 0) if isinstance(item.get("values"), list) else item.get("value", 0)
    return data


async def _fetch_fb_insights(
    post_id: str,
    access_token: str,
    client: httpx.AsyncClient,
) -> dict:
    resp = await client.get(f"{_GRAPH}/{post_id}/insights", params={
        "metric":       _FB_METRICS,
        "access_token": access_token,
    })
    if resp.status_code != 200:
        log.warning("fb_insights_failed", post_id=post_id, status=resp.status_code)
        return {}
    data = {}
    for item in resp.json().get("data", []):
        data[item["name"]] = item.get("values", [{}])[0].get("value", 0) if isinstance(item.get("values"), list) else item.get("value", 0)
    return data


def _build_metric(post: Post, raw: dict, platform: Platform, now: datetime) -> Optional[Metric]:
    """Map raw Graph API fields onto our Metric model columns."""
    if not raw:
        return None

    if platform == Platform.instagram:
        reach       = int(raw.get("reach", 0) or 0)
        impressions = int(raw.get("impressions", 0) or 0)
        engagement  = int((raw.get("likes") or 0) + (raw.get("comments") or 0) + (raw.get("shares") or 0))
        conversions = int(raw.get("saved", 0) or 0)
        ctr         = round(engagement / impressions, 4) if impressions > 0 else 0.0

    elif platform == Platform.facebook:
        reach       = int(raw.get("post_impressions_unique", 0) or 0)
        impressions = int(raw.get("post_impressions", 0) or 0)
        engagement  = int(raw.get("post_engaged_users", 0) or 0)
        conversions = int(raw.get("post_clicks", 0) or 0)
        ctr         = round(engagement / impressions, 4) if impressions > 0 else 0.0
    else:
        return None

    return Metric(
        post_id    = post.id,
        platform   = platform,
        reach      = reach,
        engagement = engagement,
        ctr        = ctr,
        conversions= conversions,
        fetched_at = now,
    )


async def sync_published_posts(db: AsyncSession) -> int:
    """
    Fetch insights for all published posts that have a platform_post_id.
    Returns the number of posts successfully synced.
    Skips posts synced within the last 6 hours to avoid rate limits.
    """
    token = await _get_token(db)
    if not token:
        log.warning("insights_sync_skipped", reason="No Meta token available")
        return 0

    now         = datetime.now(timezone.utc)
    cutoff      = now - timedelta(hours=6)

    # Load published Instagram + Facebook posts that have platform_post_id
    result = await db.execute(
        select(Post).where(
            Post.status == PostStatus.published,
            Post.platform.in_([Platform.instagram, Platform.facebook]),
        )
    )
    posts = result.scalars().all()

    synced = 0
    async with httpx.AsyncClient(timeout=20) as client:
        for post in posts:
            meta     = post.metadata_json or {}
            media_id = meta.get("platform_post_id")
            if not media_id:
                continue

            # Skip if recently synced
            last_fetch_str = meta.get("insights_fetched_at")
            if last_fetch_str:
                try:
                    last_fetch = datetime.fromisoformat(last_fetch_str)
                    if last_fetch.tzinfo is None:
                        last_fetch = last_fetch.replace(tzinfo=timezone.utc)
                    if last_fetch > cutoff:
                        continue
                except ValueError:
                    pass

            try:
                if post.platform == Platform.instagram:
                    raw = await _fetch_ig_insights(media_id, token, client)
                else:
                    raw = await _fetch_fb_insights(media_id, token, client)

                metric = _build_metric(post, raw, post.platform, now)
                if metric:
                    db.add(metric)
                    # Mark synced timestamp
                    updated_meta = {**meta, "insights_fetched_at": now.isoformat()}
                    post.metadata_json = updated_meta
                    synced += 1

            except Exception as exc:
                log.error("insights_sync_post_failed", post_id=str(post.id), error=str(exc))

    await db.flush()
    log.info("insights_sync_complete", synced=synced, total=len(posts))
    return synced


async def run_insights_sync() -> int:
    """Standalone entry point for APScheduler."""
    from backend.db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        count = await sync_published_posts(db)
        await db.commit()
        return count
