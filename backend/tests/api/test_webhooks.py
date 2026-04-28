"""
Webhook tests — validates X-Webhook-Secret header enforcement.
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


VALID_HEADERS = {"X-Webhook-Secret": settings.WEBHOOK_SECRET}

PAYLOAD = {
    "post_id": "00000000-0000-0000-0000-000000000001",
    "platform": "xiaohongshu",
    "post_url": "https://xiaohongshu.com/post/123",
}


async def test_publish_confirmation_missing_secret(client):
    r = await client.post("/api/v1/webhooks/publish-confirmation", json=PAYLOAD)
    assert r.status_code == 422   # X-Webhook-Secret header missing → 422


async def test_publish_confirmation_wrong_secret(client):
    r = await client.post(
        "/api/v1/webhooks/publish-confirmation",
        json=PAYLOAD,
        headers={"X-Webhook-Secret": "wrong-secret"},
    )
    assert r.status_code == 403


async def test_publish_confirmation_correct_secret(client):
    r = await client.post(
        "/api/v1/webhooks/publish-confirmation",
        json=PAYLOAD,
        headers=VALID_HEADERS,
    )
    # Without DB → 500; auth/secret check passed (not 403)
    assert r.status_code != 403


async def test_platform_metric_wrong_secret(client):
    r = await client.post(
        "/api/v1/webhooks/platform-metric",
        json={"post_id": "00000000-0000-0000-0000-000000000001", "platform": "instagram"},
        headers={"X-Webhook-Secret": "bad"},
    )
    assert r.status_code == 403


async def test_platform_metric_correct_secret(client):
    r = await client.post(
        "/api/v1/webhooks/platform-metric",
        json={"post_id": "00000000-0000-0000-0000-000000000001", "platform": "instagram"},
        headers=VALID_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["received"] is True
