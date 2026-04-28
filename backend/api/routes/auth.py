"""
Auth routes.

POST /auth/token      — simple password → JWT (backward-compat, used by frontend)
POST /auth/login      — OAuth2 form (username/email + password) for Swagger UI
GET  /auth/me         — current user info
POST /auth/refresh    — extend session
POST /auth/users      — admin: create team member
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import create_access_token, hash_password, verify_password
from backend.api.deps import get_current_admin, get_current_user, get_db
from backend.api.schemas.auth import TokenResponse, UserCreate, UserOut, UserUpdate
from backend.config import settings
from backend.db.models import User

log    = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])


# ── helpers ───────────────────────────────────────────────────────────────────

class PasswordTokenRequest(BaseModel):
    password: str


def _token_response(user_email: str, role: str, user_id: Optional[str] = None) -> TokenResponse:
    token, expires_in = create_access_token(subject=user_email, role=role, user_id=user_id)
    user_out = UserOut(
        id=uuid.UUID(user_id) if user_id else uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email=user_email,
        full_name="System Admin" if user_email == "admin@system" else None,
        role=role,
        is_active=True,
        created_at=None,
        last_login_at=None,
    )
    return TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in, user=user_out)


# ── POST /auth/token — legacy password-based (frontend uses this) ─────────────

@router.post("/token", response_model=TokenResponse, summary="Password → JWT (simple auth)")
async def login_password(body: PasswordTokenRequest) -> TokenResponse:
    if body.password != settings.API_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_response("admin@system", "admin")


# ── POST /auth/login — OAuth2 form (Swagger UI + multi-user) ──────────────────

@router.post("/login", response_model=TokenResponse, summary="OAuth2 login (email + password)")
async def login_oauth2(
    form: OAuth2PasswordRequestForm = Depends(),
    db:   AsyncSession              = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == form.username))
    user   = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    log.info("user_login", email=user.email, role=user.role)

    token, expires_in = create_access_token(
        subject=user.email, role=user.role, user_id=str(user.id)
    )
    user_out = UserOut.model_validate(user)
    return TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in, user=user_out)


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut, summary="Current user info")
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh(current_user: User = Depends(get_current_user)) -> TokenResponse:
    token, expires_in = create_access_token(
        subject=current_user.email,
        role=current_user.role,
        user_id=str(current_user.id),
    )
    user_out = UserOut.model_validate(current_user)
    return TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in, user=user_out)


# ── POST /auth/users — admin only ─────────────────────────────────────────────

@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create team member (admin only)",
)
async def create_user(
    body:         UserCreate,
    db:           AsyncSession = Depends(get_db),
    _admin:       User         = Depends(get_current_admin),
) -> UserOut:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"User '{body.email}' already exists")

    user = User(
        id=uuid.uuid4(),
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()
    log.info("user_created", email=user.email, role=user.role, by=_admin.email)
    return UserOut.model_validate(user)


# ── GET /auth/users — admin only ──────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut], summary="List users (admin only)")
async def list_users(
    db:     AsyncSession = Depends(get_db),
    _admin: User         = Depends(get_current_admin),
) -> list[UserOut]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


# ── PATCH /auth/users/{user_id} — admin only ─────────────────────────────────

@router.patch("/users/{user_id}", response_model=UserOut, summary="Update user (admin only)")
async def update_user(
    user_id: uuid.UUID,
    body:    UserUpdate,
    db:      AsyncSession = Depends(get_db),
    _admin:  User         = Depends(get_current_admin),
) -> UserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, f"User {user_id} not found")
    if body.full_name is not None: user.full_name = body.full_name
    if body.role      is not None: user.role      = body.role
    if body.is_active is not None: user.is_active = body.is_active
    await db.flush()
    return UserOut.model_validate(user)
