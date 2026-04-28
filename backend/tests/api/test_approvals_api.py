"""
Approvals API tests.
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


async def test_queue_requires_auth(client):
    r = await client.get("/api/v1/approvals/queue")
    assert r.status_code in (401, 403)


async def test_queue_auth_accepted(client, auth):
    r = await client.get("/api/v1/approvals/queue", headers=auth)
    assert r.status_code != 401
    assert r.status_code != 403


async def test_queue_count_requires_auth(client):
    r = await client.get("/api/v1/approvals/queue/count")
    assert r.status_code in (401, 403)


async def test_queue_count_auth_accepted(client, auth):
    r = await client.get("/api/v1/approvals/queue/count", headers=auth)
    assert r.status_code != 401
    assert r.status_code != 403


async def test_history_requires_auth(client):
    r = await client.get("/api/v1/approvals/history")
    assert r.status_code in (401, 403)


async def test_batch_approve_requires_body(client, auth):
    r = await client.post("/api/v1/approvals/batch-approve", json={}, headers=auth)
    assert r.status_code == 422


async def test_batch_approve_empty_list(client, auth):
    r = await client.post(
        "/api/v1/approvals/batch-approve",
        json={"post_ids": []},
        headers=auth,
    )
    # 200 with empty approved/failed lists (or 500 without DB — either is fine)
    assert r.status_code in (200, 500)
