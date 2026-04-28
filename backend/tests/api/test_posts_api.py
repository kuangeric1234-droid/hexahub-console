"""
Posts API tests.
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


async def test_list_posts_requires_auth(client):
    r = await client.get("/api/v1/posts")
    assert r.status_code in (401, 403)


async def test_list_posts_auth_accepted(client, auth):
    r = await client.get("/api/v1/posts", headers=auth)
    assert r.status_code != 401
    assert r.status_code != 403


async def test_list_posts_pagination_params(client, auth):
    r = await client.get("/api/v1/posts?page=1&page_size=10", headers=auth)
    assert r.status_code != 401


async def test_get_post_not_found(client, auth):
    r = await client.get(f"/api/v1/posts/{FAKE_UUID}", headers=auth)
    assert r.status_code in (404, 500)


async def test_update_post_requires_auth(client):
    r = await client.patch(f"/api/v1/posts/{FAKE_UUID}", json={"copy": "new copy"})
    assert r.status_code in (401, 403)


async def test_approve_requires_auth(client):
    r = await client.post(f"/api/v1/posts/{FAKE_UUID}/approve", json={})
    assert r.status_code in (401, 403)


async def test_reject_requires_feedback(client, auth):
    r = await client.post(
        f"/api/v1/posts/{FAKE_UUID}/reject",
        json={},   # missing required feedback
        headers=auth,
    )
    assert r.status_code == 422


async def test_versions_endpoint_auth_accepted(client, auth):
    r = await client.get(f"/api/v1/posts/{FAKE_UUID}/versions", headers=auth)
    assert r.status_code != 401
    assert r.status_code != 403
