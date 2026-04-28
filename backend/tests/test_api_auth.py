"""
API auth tests — updated for new JWT structure (role, iat claims).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_health_endpoint(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_login_with_correct_password_returns_token(client):
    r = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


async def test_login_with_wrong_password_returns_401(client):
    r = await client.post("/api/v1/auth/token", json={"password": "definitely-wrong"})
    assert r.status_code == 401


async def test_protected_endpoint_without_token_returns_403_or_401(client):
    r = await client.get("/api/v1/campaigns")
    assert r.status_code in (401, 403)


async def test_protected_endpoint_with_valid_token_passes_auth(client):
    login = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    token = login.json()["access_token"]
    r = await client.get("/api/v1/campaigns", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code != 401


async def test_expired_or_malformed_token_returns_401(client):
    r = await client.get(
        "/api/v1/campaigns",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert r.status_code == 401


async def test_token_contains_expected_claims(client):
    from jose import jwt

    r = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    token   = r.json()["access_token"]
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM])

    assert payload["sub"] == "admin@system"
    assert payload["role"] == "admin"
    assert "exp" in payload
    assert "iat" in payload
