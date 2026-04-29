"""
Facebook publisher — posts to a Facebook Page via Meta Graph API.
Requires: FACEBOOK_PAGE_ID, FACEBOOK_PAGE_ACCESS_TOKEN
"""
from __future__ import annotations

import structlog
import httpx

from backend.services.publishers.base import PublishResult

log = structlog.get_logger()

_GRAPH_BASE = "https://graph.facebook.com/v19.0"


async def FacebookPublisher(copy: str, visual_url: str | None, access_token: str, page_id: str) -> PublishResult:
    if not access_token or not page_id:
        return PublishResult(success=False, error="FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN not configured")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if visual_url:
                resp = await client.post(
                    f"{_GRAPH_BASE}/{page_id}/photos",
                    params={
                        "url": visual_url,
                        "message": copy,
                        "access_token": access_token,
                    },
                )
            else:
                resp = await client.post(
                    f"{_GRAPH_BASE}/{page_id}/feed",
                    params={
                        "message": copy,
                        "access_token": access_token,
                    },
                )
            resp.raise_for_status()
            post_id = resp.json().get("id", "")
            log.info("facebook_published", post_id=post_id)
            return PublishResult(
                success=True,
                post_url=f"https://www.facebook.com/{post_id}",
                platform_post_id=post_id,
            )
    except httpx.HTTPStatusError as e:
        error = f"Facebook API error {e.response.status_code}: {e.response.text}"
        log.error("facebook_publish_failed", error=error)
        return PublishResult(success=False, error=error)
    except Exception as e:
        log.error("facebook_publish_failed", error=str(e))
        return PublishResult(success=False, error=str(e))
