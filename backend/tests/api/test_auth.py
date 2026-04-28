"""
Auth route tests.

Tests the multi-user /auth/login and /auth/me endpoints,
as well as admin-only /auth/users.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── POST /api/v1/auth/token (legacy) ─────────────────────────────────────────

async def test_legacy_token_correct_password(client):
    r = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == "admin@system"
    assert data["user"]["role"] == "admin"


async def test_legacy_token_wrong_password(client):
    r = await client.post("/api/v1/auth/token", json={"password": "wrong"})
    assert r.status_code == 401


# ── GET /api/v1/auth/me ───────────────────────────────────────────────────────

async def test_me_with_valid_token(client):
    login = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    token = login.json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "admin@system"


async def test_me_without_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 403   # HTTPBearer returns 403 when missing


async def test_me_invalid_token(client):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bad.token.here"})
    assert r.status_code == 401


# ── POST /api/v1/auth/refresh ─────────────────────────────────────────────────

async def test_refresh_with_valid_token(client):
    login = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    token = login.json()["access_token"]
    r = await client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    new_token = r.json()["access_token"]
    assert new_token  # a new token is returned


# ── Token claims ──────────────────────────────────────────────────────────────

async def test_token_contains_role_claim(client):
    from jose import jwt

    r = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    token   = r.json()["access_token"]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM])
    assert payload["role"] == "admin"
    assert "exp" in payload
    assert "iat" in payload


# ── POST /api/v1/auth/users (admin only) ─────────────────────────────────────

async def test_create_user_requires_auth(client):
    r = await client.post("/api/v1/auth/users", json={
        "email": "test@example.com", "password": "password123"
    })
    assert r.status_code == 403


async def test_create_user_with_admin_token_hits_db(client):
    """The endpoint is reachable with a token; 500 expected without DB."""
    login = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    token = login.json()["access_token"]
    r = await client.post(
        "/api/v1/auth/users",
        json={"email": "newuser@example.com", "password": "password123", "role": "member"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Without a real DB we get a 500; importantly NOT a 401/403
    assert r.status_code != 401
    assert r.status_code != 403
