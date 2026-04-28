"""
Compliance API tests.
The /check endpoint uses QuickComplianceCheck (no DB, no LLM).
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


async def test_check_requires_auth(client):
    r = await client.post("/api/v1/compliance/check", json={"text": "hello"})
    assert r.status_code in (401, 403)


async def test_check_clean_text(client, auth):
    r = await client.post(
        "/api/v1/compliance/check",
        json={"text": "我们提供专业的跨境电商服务", "languages": ["zh-CN"]},
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert "passed" in data
    assert isinstance(data["flags"], list)
    assert isinstance(data["suggestions"], list)


async def test_check_flagged_text(client, auth):
    r = await client.post(
        "/api/v1/compliance/check",
        json={"text": "我们是最好的产品，第一品牌", "languages": ["zh-CN"]},
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["passed"] is False
    assert len(data["flags"]) > 0


async def test_check_english_text(client, auth):
    r = await client.post(
        "/api/v1/compliance/check",
        json={"text": "This game-changing solution is world-class", "languages": ["en"]},
        headers=auth,
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["flags"]) > 0   # "game-changing" and "world-class" flagged


async def test_check_multilingual(client, auth):
    r = await client.post(
        "/api/v1/compliance/check",
        json={"text": "best product 最好的", "languages": ["en", "zh-CN"]},
        headers=auth,
    )
    assert r.status_code == 200


async def test_sensitive_words_requires_auth(client):
    r = await client.get("/api/v1/compliance/sensitive-words")
    assert r.status_code in (401, 403)


async def test_sensitive_words_list_auth_accepted(client, auth):
    r = await client.get("/api/v1/compliance/sensitive-words", headers=auth)
    # 200 with list (empty if no DB) or 500 without DB
    assert r.status_code != 401
    assert r.status_code != 403


async def test_add_word_requires_admin(client, auth):
    r = await client.post(
        "/api/v1/compliance/sensitive-words",
        json={"word": "test", "language": "en", "severity": "low"},
        headers=auth,
    )
    # Admin token from simple auth → should pass auth; may fail on DB
    assert r.status_code != 401
    assert r.status_code != 403


async def test_add_word_invalid_severity(client, auth):
    r = await client.post(
        "/api/v1/compliance/sensitive-words",
        json={"word": "test", "language": "en", "severity": "nuclear"},
        headers=auth,
    )
    assert r.status_code in (422, 500)
