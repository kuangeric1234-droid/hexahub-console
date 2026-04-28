"""
Shared FastAPI dependencies.

get_db            → async SQLAlchemy session (auto-commit/rollback)
get_current_user  → validates Bearer JWT, returns User (or synthetic admin)
get_current_admin → get_current_user + role == "admin" guard
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import decode_access_token
from backend.config import settings
from backend.db.database import AsyncSessionLocal
from backend.db.models import User

log = structlog.get_logger()

_bearer = HTTPBearer()

# Synthetic admin returned when a legacy single-password JWT is used
# (sub = "admin@system", no user_id claim, no DB row required)
_LEGACY_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Database ──────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Auth ───────────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db:          AsyncSession                 = Depends(get_db),
) -> User:
    """Decode JWT → return User. Handles both legacy and multi-user tokens."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise exc

    sub:     str | None = payload.get("sub")
    user_id: str | None = payload.get("user_id")

    if not sub:
        raise exc

    # ── New-style token: contains user_id → DB lookup ──────────────────────
    if user_id:
        user = await db.get(User, uuid.UUID(user_id))
        if not user or not user.is_active:
            raise exc
        return user

    # ── Legacy token: sub == "admin@system" → synthetic admin User ─────────
    if sub == "admin@system" or sub == "admin":
        synthetic = User()
        synthetic.id            = _LEGACY_ADMIN_ID
        synthetic.email         = "admin@system"
        synthetic.hashed_password = ""
        synthetic.full_name     = "Legacy Admin"
        synthetic.role          = "admin"
        synthetic.is_active     = True
        synthetic.created_at    = None
        synthetic.last_login_at = None
        return synthetic

    # ── Email sub → DB lookup ──────────────────────────────────────────────
    result = await db.execute(select(User).where(User.email == sub))
    user   = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise exc
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return current_user
