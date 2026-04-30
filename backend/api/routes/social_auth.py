"""
Social media OAuth — read-only post fetching for Content DNA scanner.

GET  /social/meta/auth-url        → returns Facebook OAuth URL
POST /social/meta/fetch-posts     → { code, redirect_uri } → fetched posts
"""
from __future__ import annotations

from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_current_user
from backend.config import settings
from backend.db.models import User

log    = structlog.get_logger()
router = APIRouter(prefix="/social", tags=["social"])

_META_AUTH_URL  = "https://www.facebook.com/v21.0/dialog/oauth"
_META_TOKEN_URL = "https://graph.facebook.com/v21.0/oauth/access_token"
_GRAPH_BASE     = "https://graph.facebook.com/v21.0"

_META_SCOPES = "instagram_basic,pages_show_list,pages_read_engagement"


# ── Request / Response models ──────────────────────────────────────────────────

class AuthUrlResponse(BaseModel):
    url: str


class FetchPostsRequest(BaseModel):
    code:         str
    redirect_uri: str


class FetchedPost(BaseModel):
    platform:   str
    text:       str
    created_at: str | None = None


class FetchPostsResponse(BaseModel):
    posts:        list[FetchedPost]
    platform:     str
    account_name: str | None = None


# ── Meta OAuth ─────────────────────────────────────────────────────────────────

@router.get("/meta/auth-url", response_model=AuthUrlResponse,
            summary="Get Facebook OAuth URL for post scanning")
async def meta_auth_url(
    redirect_uri: str,
    state:        str,
    _:            User = Depends(get_current_user),
) -> AuthUrlResponse:
    if not settings.META_APP_ID:
        raise HTTPException(503, "META_APP_ID not configured in backend/.env")

    qs = urlencode({
        "client_id":     settings.META_APP_ID,
        "redirect_uri":  redirect_uri,
        "scope":         _META_SCOPES,
        "response_type": "code",
        "state":         state,
    })
    return AuthUrlResponse(url=f"{_META_AUTH_URL}?{qs}")


@router.post("/meta/fetch-posts", response_model=FetchPostsResponse,
             summary="Exchange OAuth code for token and fetch Meta posts")
async def meta_fetch_posts(
    body: FetchPostsRequest,
    _:    User = Depends(get_current_user),
) -> FetchPostsResponse:
    if not settings.META_APP_ID or not settings.META_APP_SECRET:
        raise HTTPException(503, "META_APP_ID / META_APP_SECRET not configured")

    async with httpx.AsyncClient(timeout=20) as client:
        # Exchange authorisation code for user access token
        token_resp = await client.get(_META_TOKEN_URL, params={
            "client_id":     settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri":  body.redirect_uri,
            "code":          body.code,
        })
        if token_resp.status_code != 200:
            log.error("meta_token_exchange_failed", status=token_resp.status_code, body=token_resp.text)
            raise HTTPException(400, f"Meta token exchange failed: {token_resp.text}")

        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(400, "No access_token in Meta response")

        posts: list[FetchedPost] = []
        account_name: str | None = None

        # Get all Facebook Pages the user administers
        pages_resp = await client.get(f"{_GRAPH_BASE}/me/accounts", params={
            "access_token": access_token,
            "fields":       "id,name,access_token,instagram_business_account",
        })
        pages = pages_resp.json().get("data", []) if pages_resp.status_code == 200 else []

        for page in pages:
            page_token = page.get("access_token", access_token)
            if not account_name:
                account_name = page.get("name")

            # Facebook Page posts
            fb_resp = await client.get(f"{_GRAPH_BASE}/{page['id']}/posts", params={
                "access_token": page_token,
                "fields":       "message,created_time",
                "limit":        25,
            })
            if fb_resp.status_code == 200:
                for p in fb_resp.json().get("data", []):
                    msg = (p.get("message") or "").strip()
                    if msg:
                        posts.append(FetchedPost(
                            platform="facebook",
                            text=msg,
                            created_at=p.get("created_time"),
                        ))

            # Instagram Business posts (if page has a linked IG account)
            ig_account = page.get("instagram_business_account")
            if ig_account:
                ig_resp = await client.get(f"{_GRAPH_BASE}/{ig_account['id']}/media", params={
                    "access_token": page_token,
                    "fields":       "caption,timestamp,media_type",
                    "limit":        25,
                })
                if ig_resp.status_code == 200:
                    for m in ig_resp.json().get("data", []):
                        caption = (m.get("caption") or "").strip()
                        if caption:
                            posts.append(FetchedPost(
                                platform="instagram",
                                text=caption,
                                created_at=m.get("timestamp"),
                            ))

    log.info("meta_posts_fetched", count=len(posts), account=account_name)
    return FetchPostsResponse(posts=posts, platform="meta", account_name=account_name)
