"""
Brand / skills API tests.
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


@pytest.fixture
async def auth(client):
    r = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_get_context_requires_auth(client):
    r = await client.get("/api/v1/brand/context")
    assert r.status_code in (401, 403)


async def test_get_context_auth_accepted(client, auth):
    r = await client.get("/api/v1/brand/context", headers=auth)
    assert r.status_code == 200
    assert "content" in r.json()


async def test_list_skills_auth_accepted(client, auth):
    r = await client.get("/api/v1/brand/skills", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert "external" in data
    assert "custom" in data
    assert isinstance(data["external"], list)
    assert isinstance(data["custom"], list)


async def test_get_skill_content_not_found(client, auth):
    r = await client.get("/api/v1/brand/skills/nonexistent-skill-xyz", headers=auth)
    assert r.status_code == 404


async def test_update_context_auth_accepted(client, auth):
    r = await client.put(
        "/api/v1/brand/context",
        json={"content": "# Test Brand Context\nThis is a test."},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["content"].startswith("# Test Brand Context")
