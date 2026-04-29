"""
Post publishing scheduler.
Runs every minute, finds posts with status=scheduled and scheduled_at <= now(),
and publishes them via the appropriate platform publisher.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import Platform, Post, PostStatus

log = structlog.get_logger()

scheduler = AsyncIOScheduler(timezone="UTC")


async def _publish_post(post: Post, db) -> None:
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
        result = await InstagramPublisher(
            copy=post.copy or "",
            visual_url=post.visual_url,
            access_token=settings.META_ACCESS_TOKEN,
            ig_user_id=settings.META_IG_USER_ID,
        )
    elif platform == Platform.facebook:
        result = await FacebookPublisher(
            copy=post.copy or "",
            visual_url=post.visual_url,
            access_token=settings.FACEBOOK_PAGE_ACCESS_TOKEN,
            page_id=settings.FACEBOOK_PAGE_ID,
        )
    else:
        log.warning("scheduler_no_publisher", platform=platform.value, post_id=str(post.id))
        return

    meta = dict(post.metadata_json or {})

    if result.success:
        post.status = PostStatus.published
        meta["external_url"] = result.post_url
        meta["platform_post_id"] = result.platform_post_id
        meta["published_at"] = datetime.now(timezone.utc).isoformat()
        log.info("scheduler_published", post_id=str(post.id), platform=platform.value, url=result.post_url)
    else:
        post.status = PostStatus.failed
        meta["publish_error"] = result.error
        meta["failed_at"] = datetime.now(timezone.utc).isoformat()
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

        for post in posts:
            try:
                await _publish_post(post, db)
            except Exception as exc:
                post.status = PostStatus.failed
                meta = dict(post.metadata_json or {})
                meta["publish_error"] = str(exc)
                post.metadata_json = meta
                log.error("scheduler_exception", post_id=str(post.id), error=str(exc))

        await db.commit()
