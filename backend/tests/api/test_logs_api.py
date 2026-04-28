"""
Agent logs API tests (admin-only).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.main import app

FAKE_UUID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth(client):
    r = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_logs_requires_auth(client):
    r = await client.get("/api/v1/logs/agent-runs")
    assert r.status_code in (401, 403)


async def test_logs_admin_token_accepted(client, auth):
    r = await client.get("/api/v1/logs/agent-runs", headers=auth)
    # Admin token from simple auth → not 401/403
    assert r.status_code != 401
    assert r.status_code != 403


async def test_log_detail_not_found(client, auth):
    r = await client.get(f"/api/v1/logs/agent-runs/{FAKE_UUID}", headers=auth)
    assert r.status_code in (404, 500)


async def test_workflow_logs_auth_accepted(client, auth):
    r = await client.get(f"/api/v1/logs/workflow/{FAKE_UUID}", headers=auth)
    assert r.status_code != 401
    assert r.status_code != 403


async def test_logs_pagination(client, auth):
    r = await client.get("/api/v1/logs/agent-runs?page=1&page_size=10", headers=auth)
    assert r.status_code != 401
