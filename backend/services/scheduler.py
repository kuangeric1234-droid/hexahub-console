"""
Post publishing scheduler.
Runs every minute, finds posts with status=scheduled and scheduled_at <= now(),
and publishes them via the appropriate platform publisher.

Meta credentials are loaded from the social_connections table (set via
/social/meta/connect). Env vars META_ACCESS_TOKEN / META_IG_USER_ID /
FACEBOOK_PAGE_ACCESS_TOKEN / FACEBOOK_PAGE_ID are used as a fallback if no
DB connection exists (backward compatible during transition).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import Platform, Post, PostStatus, SocialConnection

log = structlog.get_logger()

scheduler = AsyncIOScheduler(timezone="UTC")


@dataclass
class _MetaCreds:
    page_access_token: str
    ig_user_id:        str
    page_id:           str


async def _load_meta_creds(db: AsyncSession) -> Optional[_MetaCreds]:
    """
    Return Meta credentials, preferring the DB-stored OAuth connection.
    Falls back to env vars so existing deployments keep working until the
    OAuth connect flow is completed.
    Returns None if neither source has credentials.
    """
    result = await db.execute(
        select(SocialConnection).where(SocialConnection.provider == "meta")
    )
    conn = result.scalar_one_or_none()

    if conn and conn.page_access_token:
        return _MetaCreds(
            page_access_token = conn.page_access_token,
            ig_user_id        = conn.ig_user_id or "",
            page_id           = conn.page_id or "",
        )

    # Env var fallback
    token   = settings.META_ACCESS_TOKEN
    ig_id   = settings.META_IG_USER_ID
    page_id = settings.FACEBOOK_PAGE_ID
    if token:
        return _MetaCreds(page_access_token=token, ig_user_id=ig_id, page_id=page_id)

    return None


async def _publish_post(post: Post, db: AsyncSession, meta_creds: Optional[_MetaCreds]) -> None:
    """Dispatch to the correct platform publisher and update post status."""
    from backend.services.publishers.linkedin import LinkedInPublisher
    from backend.services.publishers.instagram import InstagramPublisher
    from backend.services.publishers.facebook import FacebookPublisher

    platform = post.platform

    if platform == Platform.linkedin:
        result = await LinkedInPublisher(
            copy=post.copy or "",
            visual_url=post.visual_url,
            access_token=settings.LINKEDIN_ACCESS_TOKEN,
            person_urn=settings.LINKEDIN_PERSON_URN,
        )
    elif platform == Platform.instagram:
        if not meta_creds or not meta_creds.ig_user_id:
            log.error(
                "scheduler_meta_not_connected",
                post_id=str(post.id),
                hint="Connect via /social/meta/connect or set META_ACCESS_TOKEN + META_IG_USER_ID",
            )
            post.status = PostStatus.failed
            meta = dict(post.metadata_json or {})
            meta["publish_error"] = "Meta account not connected — visit Settings to connect."
            post.metadata_json = meta
            await db.flush()
            return
        result = await InstagramPublisher(
            copy=post.copy or "",
            visual_url=post.visual_url,
            access_token=meta_creds.page_access_token,
            ig_user_id=meta_creds.ig_user_id,
        )
        # Cross-post to Facebook automatically if page_id is available
        if result.success and meta_creds.page_id:
            fb_result = await FacebookPublisher(
                copy=post.copy or "",
                visual_url=post.visual_url,
                access_token=meta_creds.page_access_token,
                page_id=meta_creds.page_id,
            )
            meta = dict(post.metadata_json or {})
            if fb_result.success:
                meta["facebook_post_id"]  = fb_result.platform_post_id
                meta["facebook_post_url"] = fb_result.post_url
                log.info("scheduler_facebook_crosspost", post_id=str(post.id), fb_post_id=fb_result.platform_post_id)
            else:
                meta["facebook_crosspost_error"] = fb_result.error
                log.warning("scheduler_facebook_crosspost_failed", post_id=str(post.id), error=fb_result.error)
            post.metadata_json = meta
    elif platform == Platform.facebook:
        if not meta_creds or not meta_creds.page_id:
            log.error(
                "scheduler_meta_not_connected",
                post_id=str(post.id),
                hint="Connect via /social/meta/connect or set FACEBOOK_PAGE_ACCESS_TOKEN + FACEBOOK_PAGE_ID",
            )
            post.status = PostStatus.failed
            meta = dict(post.metadata_json or {})
            meta["publish_error"] = "Meta account not connected — visit Settings to connect."
            post.metadata_json = meta
            await db.flush()
            return
        result = await FacebookPublisher(
            copy=post.copy or "",
            visual_url=post.visual_url,
            access_token=meta_creds.page_access_token,
            page_id=meta_creds.page_id,
        )
    else:
        log.warning("scheduler_no_publisher", platform=platform.value, post_id=str(post.id))
        return

    meta = dict(post.metadata_json or {})

    if result.success:
        post.status = PostStatus.published
        meta["external_url"]      = result.post_url
        meta["platform_post_id"]  = result.platform_post_id
        meta["published_at"]      = datetime.now(timezone.utc).isoformat()
        log.info("scheduler_published", post_id=str(post.id), platform=platform.value, url=result.post_url)
    else:
        post.status = PostStatus.failed
        meta["publish_error"] = result.error
        meta["failed_at"]     = datetime.now(timezone.utc).isoformat()
        log.error("scheduler_publish_failed", post_id=str(post.id), platform=platform.value, error=result.error)

    post.metadata_json = meta
    await db.flush()


async def publish_due_posts() -> None:
    """Called every minute — publishes all posts whose scheduled_at has passed."""
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Post)
            .where(Post.status == PostStatus.scheduled)
            .where(Post.scheduled_at <= now)
        )
        posts = result.scalars().all()

        if not posts:
            return

        log.info("scheduler_tick", due_count=len(posts))

        # Load once per tick — all Meta posts in this batch share the same credentials
        meta_creds = await _load_meta_creds(db)

        for post in posts:
            try:
                await _publish_post(post, db, meta_creds)
            except Exception as exc:
                post.status = PostStatus.failed
                meta = dict(post.metadata_json or {})
                meta["publish_error"] = str(exc)
                post.metadata_json = meta
                log.error("scheduler_exception", post_id=str(post.id), error=str(exc))

        await db.commit()
