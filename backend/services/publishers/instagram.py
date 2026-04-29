"""
Instagram publisher — posts via Meta Graph API.
Requires: META_ACCESS_TOKEN, META_IG_USER_ID
Note: Instagram requires a publicly accessible image URL. Text-only posts are not supported.
"""
from __future__ import annotations

import structlog
import httpx

from backend.services.publishers.base import PublishResult

log = structlog.get_logger()

_GRAPH_BASE = "https://graph.facebook.com/v19.0"


async def InstagramPublisher(copy: str, visual_url: str | None, access_token: str, ig_user_id: str) -> PublishResult:
    if not access_token or not ig_user_id:
        return PublishResult(success=False, error="META_ACCESS_TOKEN or META_IG_USER_ID not configured")

    if not visual_url:
        return PublishResult(success=False, error="Instagram requires an image URL — add a visual_url to this post first")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1 — create media container
            container_resp = await client.post(
                f"{_GRAPH_BASE}/{ig_user_id}/media",
                params={
                    "image_url": visual_url,
                    "caption": copy,
                    "access_token": access_token,
                },
            )
            container_resp.raise_for_status()
            container_id = container_resp.json()["id"]

            # Step 2 — publish
            publish_resp = await client.post(
                f"{_GRAPH_BASE}/{ig_user_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": access_token,
                },
            )
            publish_resp.raise_for_status()
            media_id = publish_resp.json()["id"]
            log.info("instagram_published", media_id=media_id)
            return PublishResult(
                success=True,
                post_url=f"https://www.instagram.com/p/{media_id}/",
                platform_post_id=media_id,
            )
    except httpx.HTTPStatusError as e:
        error = f"Instagram API error {e.response.status_code}: {e.response.text}"
        log.error("instagram_publish_failed", error=error)
        return PublishResult(success=False, error=error)
    except Exception as e:
        log.error("instagram_publish_failed", error=str(e))
        return PublishResult(success=False, error=str(e))
