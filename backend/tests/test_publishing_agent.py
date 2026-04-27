"""
Unit tests for PublishingAgent and platform publishers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from backend.agents.publish import (
    ManualPackagePublisher,
    PublishingAgent,
)
from backend.agents.schemas.publish import PublishInput, PublishOutput, PublishedResult
from backend.db.models import Platform


def _make_input(platform: Platform = Platform.xiaohongshu) -> PublishInput:
    return PublishInput(
        post_id=uuid4(),
        campaign_id=uuid4(),
        platform=platform,
        copy="Build locally, scale sustainably. 在澳洲落地运营，找Hexa Hub。",
        visual_url="https://example.com/image.png",
        scheduled_at=datetime(2026, 6, 15, 9, 0, tzinfo=timezone.utc),
        metadata={"topic_tags": ["#澳洲电商", "#hexahub"]},
    )


# ── ManualPackagePublisher ────────────────────────────────────────────────────

async def test_manual_publisher_returns_package_generated():
    pub    = ManualPackagePublisher()
    result = await pub.publish(_make_input(Platform.xiaohongshu))
    assert result.status == "package_generated"
    assert result.requires_manual_action is True


async def test_manual_publisher_package_contains_all_fields():
    inp    = _make_input(Platform.xiaohongshu)
    pub    = ManualPackagePublisher()
    result = await pub.publish(inp)
    pkg    = result.publishing_package
    assert pkg is not None
    assert pkg["copy"]          == inp.copy
    assert pkg["platform"]      == inp.platform.value
    assert pkg["visual_url"]    == inp.visual_url
    assert "instructions" in pkg


async def test_manual_publisher_wechat_has_instructions():
    pub    = ManualPackagePublisher()
    result = await pub.publish(_make_input(Platform.wechat_moments))
    assert "WeChat" in result.publishing_package["instructions"]


async def test_manual_publisher_sends_webhook_when_configured():
    with patch("backend.agents.publish.settings") as mock_settings:
        mock_settings.WEBHOOK_URL = "https://hook.example.com/notify"
        with patch("httpx.AsyncClient") as MockClient:
            mock_response = AsyncMock()
            mock_response.raise_for_status = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__  = AsyncMock(return_value=False)
            MockClient.return_value.post       = AsyncMock(return_value=mock_response)

            pub = ManualPackagePublisher()
            await pub.publish(_make_input(Platform.xiaohongshu))

            MockClient.return_value.post.assert_awaited_once()


async def test_manual_publisher_skips_webhook_when_url_not_set():
    with patch("backend.agents.publish.settings") as mock_settings:
        mock_settings.WEBHOOK_URL = ""
        # Should not raise even without a webhook URL
        pub = ManualPackagePublisher()
        result = await pub.publish(_make_input(Platform.xiaohongshu))
        assert result.status == "package_generated"


# ── PublishingAgent ───────────────────────────────────────────────────────────

async def test_publishing_agent_xhs_returns_publish_output():
    agent  = PublishingAgent()
    output = await agent(_make_input(Platform.xiaohongshu))
    assert isinstance(output, PublishOutput)
    assert output.requires_manual_action is True


async def test_publishing_agent_wechat_returns_publish_output():
    agent  = PublishingAgent()
    output = await agent(_make_input(Platform.wechat_moments))
    assert isinstance(output, PublishOutput)
    assert output.requires_manual_action is True


async def test_publishing_agent_not_configured_platform_does_not_raise():
    """LinkedIn/Meta/WordPress stubs raise NotImplementedError — agent captures it."""
    agent  = PublishingAgent()
    output = await agent(_make_input(Platform.linkedin))
    assert output.result.status == "not_configured"
    assert "not configured" in (output.result.error or "").lower()


async def test_publishing_agent_raises_for_unknown_platform():
    """There is no publisher registered for an unknown platform value."""
    agent = PublishingAgent()
    inp   = _make_input(Platform.linkedin)
    # Directly remove the platform from the registry to simulate unknown
    original = PublishingAgent._PUBLISHERS.pop(Platform.linkedin, None)
    try:
        with pytest.raises(ValueError, match="No publisher"):
            await agent(inp)
    finally:
        if original:
            PublishingAgent._PUBLISHERS[Platform.linkedin] = original


async def test_post_id_propagated_to_output():
    inp    = _make_input(Platform.xiaohongshu)
    agent  = PublishingAgent()
    output = await agent(inp)
    assert output.post_id == inp.post_id
