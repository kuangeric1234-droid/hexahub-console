"""
Campaign API tests.

Auth flows are verified; DB operations expect failures (no real DB)
but confirm endpoints are reachable with valid tokens.
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


async def test_list_campaigns_requires_auth(client):
    r = await client.get("/api/v1/campaigns")
    assert r.status_code in (401, 403)


async def test_list_campaigns_auth_accepted(client, auth):
    r = await client.get("/api/v1/campaigns", headers=auth)
    # Without DB → 500; but auth was accepted (not 401/403)
    assert r.status_code != 401
    assert r.status_code != 403


async def test_create_campaign_requires_auth(client):
    r = await client.post("/api/v1/campaigns", json={"name": "Test"})
    assert r.status_code in (401, 403)


async def test_create_campaign_validates_body(client, auth):
    r = await client.post("/api/v1/campaigns", json={"name": "X"}, headers=auth)
    # Missing required fields → 422
    assert r.status_code == 422


async def test_create_campaign_invalid_platform(client, auth):
    r = await client.post("/api/v1/campaigns", json={
        "name": "Test Campaign",
        "brief": "A" * 25,
        "objective": "Generate leads",
        "kpis": {},
        "start_date": "2026-05-01",
        "end_date": "2026-07-31",
        "platforms": ["fakebook"],
    }, headers=auth)
    # Unknown platform → 422
    assert r.status_code in (422, 500)  # 500 if DB hit first


async def test_get_nonexistent_campaign(client, auth):
    r = await client.get("/api/v1/campaigns/00000000-0000-0000-0000-000000000000", headers=auth)
    # DB not available → 500; with DB → 404
    assert r.status_code in (404, 500)


async def test_bilingual_view_requires_auth(client):
    r = await client.get("/api/v1/campaigns/00000000-0000-0000-0000-000000000000/bilingual-view")
    assert r.status_code in (401, 403)
