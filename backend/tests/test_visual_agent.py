"""
Unit tests for VisualAgent.

LLM calls are mocked. Image provider calls are tested with StubImageProvider
and a custom MockImageProvider.
"""
from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.agents.schemas.visual import VisualInput, VisualOutput
from backend.agents.visual import ImageProvider, StubImageProvider, VisualAgent
from backend.db.models import Platform
from tests.conftest import make_mock_llm

MOCK_VISUAL_JSON = {
    "description":  "Wide-angle shot of Hexa Hub's warehouse floor at Huntingdale. Three workers scanning packages at fulfilment stations. Natural overhead lighting. Clean, minimal white walls.",
    "style_notes":  "White and charcoal palette. Overhead fluorescent light, shadows soft. Composition: rule of thirds, operations in foreground, hexagon signage mid-ground.",
    "text_overlay": "",
    "dimensions":   "1080x1080",
    "alt_text":     "Workers fulfilling orders at Hexa Hub warehouse, Huntingdale Melbourne",
}


def _make_input(platform: Platform = Platform.instagram, generate_image: bool = False) -> VisualInput:
    return VisualInput(
        post_id=uuid4(),
        platform=platform,
        copy="Operations that actually work. DM us to see the floor.",
        pillar_name="Operations",
        content_brief="Show the warehouse floor in action — real people, real fulfilment.",
        generate_image=generate_image,
    )


# ── happy path — brief only ───────────────────────────────────────────────────

async def test_visual_agent_returns_visual_output():
    agent  = VisualAgent(llm_client=make_mock_llm(MOCK_VISUAL_JSON))
    output = await agent(_make_input())
    assert isinstance(output, VisualOutput)


async def test_brief_fields_are_populated():
    agent  = VisualAgent(llm_client=make_mock_llm(MOCK_VISUAL_JSON))
    output = await agent(_make_input())
    brief  = output.visual_brief
    assert brief.description
    assert brief.alt_text
    assert brief.dimensions


async def test_image_url_is_none_when_generate_false():
    agent  = VisualAgent(llm_client=make_mock_llm(MOCK_VISUAL_JSON))
    output = await agent(_make_input(generate_image=False))
    assert output.image_url is None
    assert output.provider_used is None


# ── image generation ──────────────────────────────────────────────────────────

async def test_stub_provider_returns_url_when_generate_true():
    agent  = VisualAgent(
        llm_client=make_mock_llm(MOCK_VISUAL_JSON),
        image_provider=StubImageProvider(),
    )
    output = await agent(_make_input(generate_image=True))
    assert output.image_url is not None
    assert output.provider_used == "stub"


async def test_custom_provider_is_called():
    class RecordingProvider(ImageProvider):
        called_with: list = []

        async def generate(self, brief: str, dimensions: str) -> str:
            self.called_with.append((brief, dimensions))
            return "https://example.com/image.png"

        @property
        def provider_name(self) -> str:
            return "recording"

    provider = RecordingProvider()
    agent    = VisualAgent(
        llm_client=make_mock_llm(MOCK_VISUAL_JSON),
        image_provider=provider,
    )
    await agent(_make_input(generate_image=True))
    assert len(provider.called_with) == 1


async def test_provider_not_called_when_generate_false():
    class NeverCallProvider(ImageProvider):
        async def generate(self, brief: str, dimensions: str) -> str:
            raise AssertionError("Should not have been called")

        @property
        def provider_name(self) -> str:
            return "never"

    agent = VisualAgent(
        llm_client=make_mock_llm(MOCK_VISUAL_JSON),
        image_provider=NeverCallProvider(),
    )
    output = await agent(_make_input(generate_image=False))
    assert output.image_url is None


# ── platform dimension mapping ────────────────────────────────────────────────

@pytest.mark.parametrize("platform,expected_dim", [
    (Platform.instagram,      "1080x1080"),
    (Platform.linkedin,       "1200x628"),
    (Platform.xiaohongshu,    "1242x1660"),
    (Platform.wechat_moments, "900x500"),
    (Platform.blog,           "1200x630"),
])
async def test_dimensions_match_platform(platform, expected_dim):
    visual_json = {**MOCK_VISUAL_JSON, "dimensions": expected_dim}
    agent       = VisualAgent(llm_client=make_mock_llm(visual_json))
    output      = await agent(_make_input(platform))
    assert output.visual_brief.dimensions == expected_dim


# ── post_id propagation ───────────────────────────────────────────────────────

async def test_post_id_is_propagated():
    inp    = _make_input()
    agent  = VisualAgent(llm_client=make_mock_llm(MOCK_VISUAL_JSON))
    output = await agent(inp)
    assert output.post_id == inp.post_id
