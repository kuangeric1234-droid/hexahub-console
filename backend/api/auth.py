"""
Auth utilities — password hashing and JWT encode/decode.
Not a router. Import these in deps.py and routes/auth.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    role: str = "admin",
    user_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """Return (encoded_jwt, expires_in_seconds)."""
    if expires_delta is None:
        expires_delta = timedelta(hours=settings.JWT_EXPIRY_HOURS)
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + expires_delta,
    }
    if user_id:
        payload["user_id"] = user_id
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict:
    """Decode and validate JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM])
