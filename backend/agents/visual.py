"""
VisualAgent

Input:  VisualInput  (copy + platform + brief)
Output: VisualOutput (LLM-generated image brief + optional generated image URL)

Image generation is behind the ImageProvider interface so providers are
swappable without touching agent code.  The default provider is StubImageProvider
(returns a placeholder URL).  Wire up OpenAIImageProvider in production.

Usage::

    # Brief only (no image generation)
    agent  = VisualAgent()
    output = await agent(VisualInput(post_id=..., platform=..., ..., generate_image=False))

    # With image generation
    agent  = VisualAgent(image_provider=OpenAIImageProvider())
    output = await agent(VisualInput(..., generate_image=True))
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.agents.schemas.visual import VisualBrief, VisualInput, VisualOutput
from backend.config import settings
from backend.db.models import Platform
from backend.llm.client import LLMProvider
from backend.prompts import load_prompt
from backend.utils.json_utils import extract_json

log = structlog.get_logger()

_DIMENSIONS: dict[Platform, str] = {
    Platform.linkedin:       "1200x628",
    Platform.blog:           "1200x630",
    Platform.instagram:      "1080x1080",
    Platform.xiaohongshu:    "1242x1660",
    Platform.wechat_moments: "900x500",
}


# ── Image provider interface ──────────────────────────────────────────────────

class ImageProvider(ABC):
    """Swappable image generation backend."""

    @abstractmethod
    async def generate(self, brief: str, dimensions: str) -> str:
        """Generate an image and return its public URL."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...


class StubImageProvider(ImageProvider):
    """Placeholder — returns a styled placeholder image URL. Safe for dev/test."""

    async def generate(self, brief: str, dimensions: str) -> str:
        return f"https://placehold.co/{dimensions}/2A3065/FFFFFF?text=Hexa+HUB"

    @property
    def provider_name(self) -> str:
        return "stub"


class OpenAIImageProvider(ImageProvider):
    """
    DALL-E 3 image generation.

    Requires OPENAI_API_KEY.  DALL-E 3 only supports fixed sizes so the
    requested dimensions are approximated to the nearest valid option.
    """

    _VALID_SIZES = ("1024x1024", "1024x1792", "1792x1024")

    async def generate(self, brief: str, dimensions: str) -> str:
        from openai import AsyncOpenAI  # lazy import

        size   = self._nearest_size(dimensions)
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp   = await client.images.generate(
            model="dall-e-3",
            prompt=brief,
            size=size,       # type: ignore[arg-type]
            quality="standard",
            n=1,
        )
        return resp.data[0].url or ""

    def _nearest_size(self, dims: str) -> str:
        try:
            w, h = (int(x) for x in dims.split("x"))
            if h > w:
                return "1024x1792"
            if w > h:
                return "1792x1024"
        except ValueError:
            pass
        return "1024x1024"

    @property
    def provider_name(self) -> str:
        return "openai/dall-e-3"


# ── VisualAgent ───────────────────────────────────────────────────────────────

class VisualAgent(BaseAgent[VisualInput, VisualOutput]):
    agent_name       = "visual_agent"
    default_provider = LLMProvider.ANTHROPIC

    def __init__(
        self,
        llm_client:     Optional[object]        = None,
        image_provider: Optional[ImageProvider] = None,
    ) -> None:
        super().__init__(llm_client)  # type: ignore[arg-type]
        self._image_provider = image_provider or StubImageProvider()

    async def run(self, input_data: VisualInput, db: Optional[AsyncSession] = None) -> VisualOutput:
        system_prompt = load_prompt("visual")
        user_prompt   = self._build_user_prompt(input_data)

        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.6,
        )

        raw   = extract_json(response.content)
        brief = VisualBrief(
            description  = raw.get("description",  ""),
            style_notes  = raw.get("style_notes",  ""),
            text_overlay = raw.get("text_overlay", ""),
            dimensions   = raw.get("dimensions", _DIMENSIONS.get(input_data.platform, "1080x1080")),
            alt_text     = raw.get("alt_text",     ""),
        )

        image_url: Optional[str]     = None
        provider_used: Optional[str] = None

        if input_data.generate_image:
            log.info("visual_image_generation_start", provider=self._image_provider.provider_name)
            image_url     = await self._image_provider.generate(brief.description, brief.dimensions)
            provider_used = self._image_provider.provider_name

        return VisualOutput(
            post_id=input_data.post_id,
            visual_brief=brief,
            image_url=image_url,
            provider_used=provider_used,
        )

    def _build_user_prompt(self, inp: VisualInput) -> str:
        dims = _DIMENSIONS.get(inp.platform, "1080x1080")
        return (
            f"Platform:      {inp.platform.value}  (target dimensions: {dims})\n"
            f"Content pillar: {inp.pillar_name}\n"
            f"Content brief:  {inp.content_brief}\n\n"
            f"Copy:\n{inp.copy}\n\n"
            "Generate the image brief JSON now."
        )
