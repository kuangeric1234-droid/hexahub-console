"""
Social media OAuth routes.

Content DNA scanner (read-only)
--------------------------------
GET  /social/meta/auth-url        → Facebook OAuth URL (read scopes)
POST /social/meta/fetch-posts     → exchange code, fetch + return posts

Publishing connection
---------------------
GET  /social/meta/connect-url     → Facebook OAuth URL (read + publish scopes)
POST /social/meta/connect         → exchange code, get long-lived token, store in DB
GET  /social/meta/status          → current connection info
DELETE /social/meta/disconnect    → remove stored credentials
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.config import settings
from backend.db.models import SocialConnection, User

log    = structlog.get_logger()
router = APIRouter(prefix="/social", tags=["social"])

_META_AUTH_URL  = "https://www.facebook.com/v21.0/dialog/oauth"
_META_TOKEN_URL = "https://graph.facebook.com/v21.0/oauth/access_token"
_GRAPH_BASE     = "https://graph.facebook.com/v21.0"

# Scopes for the Content DNA scanner (read-only)
_READ_SCOPES = "instagram_basic,pages_show_list,pages_read_engagement"

# Scopes for publishing — requires Meta App Review approval for
# instagram_content_publish and pages_manage_posts
_PUBLISH_SCOPES = (
    "instagram_basic,"
    "pages_show_list,"
    "pages_read_engagement,"
    "instagram_content_publish,"
    "pages_manage_posts"
)

_META_PROVIDER = "meta"


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


class ConnectRequest(BaseModel):
    code:         str
    redirect_uri: str


class ConnectResponse(BaseModel):
    connected:   bool
    page_name:   str | None = None
    ig_username: str | None = None


class StatusResponse(BaseModel):
    connected:    bool
    page_name:    str | None = None
    ig_username:  str | None = None
    connected_at: datetime | None = None


# ── Content DNA scanner (read-only) ────────────────────────────────────────────

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
        "scope":         _READ_SCOPES,
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

        pages_resp = await client.get(f"{_GRAPH_BASE}/me/accounts", params={
            "access_token": access_token,
            "fields":       "id,name,access_token,instagram_business_account",
        })
        pages = pages_resp.json().get("data", []) if pages_resp.status_code == 200 else []

        for page in pages:
            page_token = page.get("access_token", access_token)
            if not account_name:
                account_name = page.get("name")

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


# ── Publishing connection ───────────────────────────────────────────────────────

@router.get("/meta/connect-url", response_model=AuthUrlResponse,
            summary="Get Facebook OAuth URL for publishing connection")
async def meta_connect_url(
    redirect_uri: str,
    state:        str,
    _:            User = Depends(get_current_user),
) -> AuthUrlResponse:
    if not settings.META_APP_ID:
        raise HTTPException(503, "META_APP_ID not configured in backend/.env")

    qs = urlencode({
        "client_id":     settings.META_APP_ID,
        "redirect_uri":  redirect_uri,
        "scope":         _PUBLISH_SCOPES,
        "response_type": "code",
        "state":         state,
    })
    return AuthUrlResponse(url=f"{_META_AUTH_URL}?{qs}")


@router.post("/meta/connect", response_model=ConnectResponse,
             summary="Complete Meta publishing connection — exchange code and store credentials")
async def meta_connect(
    body: ConnectRequest,
    db:   AsyncSession = Depends(get_db),
    _:    User         = Depends(get_current_user),
) -> ConnectResponse:
    if not settings.META_APP_ID or not settings.META_APP_SECRET:
        raise HTTPException(503, "META_APP_ID / META_APP_SECRET not configured")

    async with httpx.AsyncClient(timeout=20) as client:
        # Step 1 — exchange code for short-lived user access token
        token_resp = await client.get(_META_TOKEN_URL, params={
            "client_id":     settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri":  body.redirect_uri,
            "code":          body.code,
        })
        if token_resp.status_code != 200:
            log.error("meta_connect_token_failed", status=token_resp.status_code, body=token_resp.text)
            raise HTTPException(400, f"Meta token exchange failed: {token_resp.text}")

        short_lived_token = token_resp.json().get("access_token")
        if not short_lived_token:
            raise HTTPException(400, "No access_token in Meta response")

        # Step 2 — exchange for long-lived user token (60-day expiry)
        ll_resp = await client.get(_META_TOKEN_URL, params={
            "grant_type":       "fb_exchange_token",
            "client_id":        settings.META_APP_ID,
            "client_secret":    settings.META_APP_SECRET,
            "fb_exchange_token": short_lived_token,
        })
        long_lived_token = (
            ll_resp.json().get("access_token") if ll_resp.status_code == 200 else short_lived_token
        )
        if ll_resp.status_code != 200:
            log.warning("meta_long_lived_token_failed", status=ll_resp.status_code)

        # Step 3 — get Page credentials (page token from a long-lived user token
        # is itself long-lived / non-expiring as long as the user doesn't revoke)
        pages_resp = await client.get(f"{_GRAPH_BASE}/me/accounts", params={
            "access_token": long_lived_token,
            "fields":       "id,name,access_token,instagram_business_account{id,username}",
        })
        if pages_resp.status_code != 200:
            raise HTTPException(400, f"Could not fetch Facebook Pages: {pages_resp.text}")

        pages = pages_resp.json().get("data", [])
        if not pages:
            raise HTTPException(400, "No Facebook Pages found for this account. Make sure you are an admin of the HexaHub page.")

        page = pages[0]
        page_id           = page.get("id")
        page_name         = page.get("name")
        page_access_token = page.get("access_token", long_lived_token)

        ig_account  = page.get("instagram_business_account") or {}
        ig_user_id  = ig_account.get("id")
        ig_username = ig_account.get("username")

    # Upsert — delete any existing Meta connection, insert fresh
    await db.execute(delete(SocialConnection).where(SocialConnection.provider == _META_PROVIDER))
    db.add(SocialConnection(
        provider          = _META_PROVIDER,
        page_id           = page_id,
        page_name         = page_name,
        page_access_token = page_access_token,
        ig_user_id        = ig_user_id,
        ig_username       = ig_username,
        connected_at      = datetime.now(timezone.utc),
        updated_at        = datetime.now(timezone.utc),
    ))

    log.info(
        "meta_connected",
        page_id=page_id,
        page_name=page_name,
        ig_user_id=ig_user_id,
        ig_username=ig_username,
    )
    return ConnectResponse(connected=True, page_name=page_name, ig_username=ig_username)


@router.get("/meta/status", response_model=StatusResponse,
            summary="Check current Meta publishing connection status")
async def meta_status(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
) -> StatusResponse:
    result = await db.execute(
        select(SocialConnection).where(SocialConnection.provider == _META_PROVIDER)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return StatusResponse(connected=False)
    return StatusResponse(
        connected=True,
        page_name=conn.page_name,
        ig_username=conn.ig_username,
        connected_at=conn.connected_at,
    )


@router.delete("/meta/disconnect", summary="Remove Meta publishing connection")
async def meta_disconnect(
    db: AsyncSession = Depends(get_db),
    _:  User         = Depends(get_current_user),
) -> dict:
    await db.execute(delete(SocialConnection).where(SocialConnection.provider == _META_PROVIDER))
    log.info("meta_disconnected")
    return {"disconnected": True}
