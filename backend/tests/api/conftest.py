"""
Fixtures for API route tests.

All tests run against the real FastAPI app but with:
- DB dependency overridden with an in-memory SQLite mock (no real DB needed)
- LLM calls never made (agents mocked at call site)
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.config import settings
from backend.main import app


# ── HTTP client ───────────────────────────────────────────────────────────────

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest.fixture
async def token(client):
    """Get a valid JWT using the simple password endpoint."""
    r = await client.post("/api/v1/auth/token", json={"password": settings.API_PASSWORD})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ── Fake DB session ───────────────────────────────────────────────────────────

class FakeSession:
    """Minimal async session stub that satisfies get/execute/add/flush/delete."""

    def __init__(self):
        self._store: dict[tuple, object] = {}

    async def get(self, model, pk):
        return self._store.get((model.__name__, pk))

    def add(self, obj):
        key = (type(obj).__name__, getattr(obj, "id", None))
        self._store[key] = obj

    async def flush(self):
        pass

    async def execute(self, stmt):
        class _Result:
            def scalars(self_inner):
                class _Scalars:
                    def all(self_inner2): return []
                    def one_or_none(self_inner2): return None
                return _Scalars()
            def all(self_inner): return []
            def scalar_one_or_none(self_inner): return None
            def scalar_one(self_inner): return 0
        return _Result()

    async def delete(self, obj):
        key = (type(obj).__name__, getattr(obj, "id", None))
        self._store.pop(key, None)

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def fake_db():
    return FakeSession()
