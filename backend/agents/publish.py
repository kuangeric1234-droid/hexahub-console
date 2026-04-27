"""
PublishingAgent

Handles platform dispatch for approved posts. Never called unless a post has
passed ComplianceAgent AND received human approval.

Platform strategy
-----------------
LinkedIn, Instagram, Blog  — real API calls (stubbed; wire up in production)
Xiaohongshu, WeChat        — no public API: generate a "publishing package"
                             (formatted copy + assets + instructions) and
                             POST to a configurable WEBHOOK_URL for manual action.

Adding a new publisher
----------------------
1. Subclass PlatformPublisher
2. Implement publish()
3. Register in PublishingAgent._PUBLISHERS
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.agents.schemas.publish import PublishInput, PublishedResult, PublishOutput
from backend.config import settings
from backend.db.models import Platform, Post, PostStatus
from backend.llm.client import LLMProvider

log = structlog.get_logger()


# ── Platform publisher interface ──────────────────────────────────────────────

class PlatformPublisher(ABC):
    @abstractmethod
    async def publish(self, inp: PublishInput) -> PublishedResult: ...


# ── Western platform publishers (API stubs) ───────────────────────────────────

class LinkedInPublisher(PlatformPublisher):
    """
    Publishes to LinkedIn via the UGC Posts API.
    Requires: LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN in .env
    """
    async def publish(self, inp: PublishInput) -> PublishedResult:
        # TODO: implement when credentials are available
        # POST https://api.linkedin.com/v2/ugcPosts
        raise NotImplementedError(
            "LinkedInPublisher not configured. "
            "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN in .env"
        )


class MetaPublisher(PlatformPublisher):
    """
    Publishes to Instagram via the Meta Graph API.
    Requires: META_ACCESS_TOKEN, META_IG_USER_ID in .env
    """
    async def publish(self, inp: PublishInput) -> PublishedResult:
        # TODO: implement
        # Step 1: POST /{ig-user-id}/media  → container_id
        # Step 2: POST /{ig-user-id}/media_publish  → media_id
        raise NotImplementedError(
            "MetaPublisher not configured. "
            "Set META_ACCESS_TOKEN and META_IG_USER_ID in .env"
        )


class WordPressPublisher(PlatformPublisher):
    """
    Publishes to WordPress via the REST API.
    Requires: WORDPRESS_URL, WORDPRESS_APP_PASSWORD in .env
    """
    async def publish(self, inp: PublishInput) -> PublishedResult:
        # TODO: implement
        # POST {WORDPRESS_URL}/wp-json/wp/v2/posts
        raise NotImplementedError(
            "WordPressPublisher not configured. "
            "Set WORDPRESS_URL and WORDPRESS_APP_PASSWORD in .env"
        )


# ── Chinese platform publisher (manual package + webhook) ─────────────────────

_PLATFORM_INSTRUCTIONS: dict[Platform, str] = {
    Platform.xiaohongshu: (
        "1. Open 小红书 app or creator.xiaohongshu.com\n"
        "2. Upload the image from visual_url (if provided)\n"
        "3. Paste the copy into the content field\n"
        "4. Add the topic tags listed in metadata.topic_tags\n"
        "5. Schedule or publish at the time shown in scheduled_at\n"
        "6. Reply 'done' to this notification with the post URL"
    ),
    Platform.wechat_moments: (
        "1. Open WeChat on your phone\n"
        "2. Tap Discover → Moments → camera icon\n"
        "3. Upload the image from visual_url (if provided)\n"
        "4. Paste the copy (max 150 chars) — it is already trimmed\n"
        "5. Post at the time shown in scheduled_at\n"
        "6. Reply 'done' to this notification with a screenshot"
    ),
}


class ManualPackagePublisher(PlatformPublisher):
    """
    XHS and WeChat Moments — no public publishing API exists.

    Generates a structured publishing package and POSTs it to WEBHOOK_URL
    so a human operator can act on it.
    """

    async def publish(self, inp: PublishInput) -> PublishedResult:
        package = self._build_package(inp)
        webhook_sent = await self._send_webhook(package)

        return PublishedResult(
            post_id=inp.post_id,
            platform=inp.platform,
            status="package_generated",
            requires_manual_action=True,
            publishing_package=package,
            published_at=None,
        )

    def _build_package(self, inp: PublishInput) -> dict:
        instructions = _PLATFORM_INSTRUCTIONS.get(inp.platform, "Manual publishing required.")
        return {
            "post_id":      str(inp.post_id),
            "campaign_id":  str(inp.campaign_id),
            "platform":     inp.platform.value,
            "scheduled_at": inp.scheduled_at.isoformat(),
            "copy":         inp.copy,
            "visual_url":   inp.visual_url,
            "metadata":     inp.metadata,
            "instructions": instructions,
        }

    async def _send_webhook(self, package: dict) -> bool:
        url = settings.WEBHOOK_URL
        if not url:
            log.warning("webhook_url_not_configured", post_id=package["post_id"])
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    url,
                    json=package,
                    headers={"Content-Type": "application/json"},
                )
                r.raise_for_status()
            log.info("webhook_sent", post_id=package["post_id"], url=url)
            return True
        except Exception as exc:
            log.error("webhook_failed", post_id=package["post_id"], error=str(exc))
            return False


# ── PublishingAgent ────────────────────────────────────────────────────────────

class PublishingAgent(BaseAgent[PublishInput, PublishOutput]):
    """
    Dispatches approved posts to the appropriate platform publisher.

    IMPORTANT: this agent must only be called after the post has passed
    ComplianceAgent AND received explicit human approval. The orchestrator
    enforces this gate — the agent itself does not re-check.
    """
    agent_name       = "publishing_agent"
    default_provider = LLMProvider.ANTHROPIC  # not used — no LLM calls

    _PUBLISHERS: dict[Platform, type[PlatformPublisher]] = {
        Platform.linkedin:       LinkedInPublisher,
        Platform.blog:           WordPressPublisher,
        Platform.instagram:      MetaPublisher,
        Platform.xiaohongshu:    ManualPackagePublisher,
        Platform.wechat_moments: ManualPackagePublisher,
    }

    async def run(
        self,
        input_data: PublishInput,
        db: Optional[AsyncSession] = None,
    ) -> PublishOutput:
        publisher_cls = self._PUBLISHERS.get(input_data.platform)
        if not publisher_cls:
            raise ValueError(f"No publisher registered for platform: {input_data.platform}")

        publisher = publisher_cls()

        try:
            result = await publisher.publish(input_data)
        except NotImplementedError as exc:
            # API not configured — record it without crashing the workflow
            log.warning("publisher_not_configured", platform=input_data.platform.value, error=str(exc))
            result = PublishedResult(
                post_id=input_data.post_id,
                platform=input_data.platform,
                status="not_configured",
                error=str(exc),
            )

        # Reflect result in DB
        if db is not None:
            try:
                post = await db.get(Post, input_data.post_id)
                if post:
                    post.status = (
                        PostStatus.published
                        if result.status in ("published", "scheduled", "package_generated")
                        else PostStatus.failed
                    )
                    if result.visual_url if hasattr(result, 'visual_url') else None:
                        post.visual_url = result.external_id
                    await db.flush()
            except Exception:
                log.warning("publish_db_update_failed", post_id=str(input_data.post_id))

        webhook_sent = (
            result.publishing_package is not None
            and result.status == "package_generated"
        )

        return PublishOutput(
            post_id=input_data.post_id,
            result=result,
            requires_manual_action=result.requires_manual_action,
            webhook_sent=webhook_sent,
        )
