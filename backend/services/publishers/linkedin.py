"""
LinkedIn publisher — posts text (with optional image URL) via UGC Posts API.
Requires: LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN
"""
from __future__ import annotations

import structlog
import httpx

from backend.services.publishers.base import PublishResult

log = structlog.get_logger()

_API_URL = "https://api.linkedin.com/v2/ugcPosts"


async def LinkedInPublisher(copy: str, visual_url: str | None, access_token: str, person_urn: str) -> PublishResult:
    if not access_token or not person_urn:
        return PublishResult(success=False, error="LINKEDIN_ACCESS_TOKEN or LINKEDIN_PERSON_URN not configured")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    if visual_url:
        media_category = "IMAGE"
        media = [{
            "status": "READY",
            "originalUrl": visual_url,
            "description": {"text": ""},
            "title": {"text": ""},
        }]
    else:
        media_category = "NONE"
        media = []

    body: dict = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": copy},
                "shareMediaCategory": media_category,
                **({"media": media} if media else {}),
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_API_URL, headers=headers, json=body)
            resp.raise_for_status()
            post_id = resp.headers.get("x-restli-id", "")
            post_url = f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else None
            log.info("linkedin_published", post_id=post_id)
            return PublishResult(success=True, post_url=post_url, platform_post_id=post_id)
    except httpx.HTTPStatusError as e:
        error = f"LinkedIn API error {e.response.status_code}: {e.response.text}"
        log.error("linkedin_publish_failed", error=error)
        return PublishResult(success=False, error=error)
    except Exception as e:
        log.error("linkedin_publish_failed", error=str(e))
        return PublishResult(success=False, error=str(e))
