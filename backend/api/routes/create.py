"""
Assisted post creation endpoint.

POST /create/assisted   — generate copy, format recommendation, visual brief
                          optionally with an uploaded image (Claude vision)
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_current_user
from backend.config import settings
from backend.db.models import User

log    = structlog.get_logger()
router = APIRouter(prefix="/create", tags=["create"])

_BRAND_CONTEXT_PATH = Path(__file__).parent.parent.parent / "prompts" / "brand_context.md"

_PLATFORM_FORMATS = {
    "linkedin":       ["article", "single_image", "carousel", "video", "document"],
    "instagram":      ["single_image", "carousel", "reel", "video"],
    "blog":           ["article", "infographic"],
    "xiaohongshu":    ["single_image", "carousel", "video"],
    "wechat_moments": ["single_image", "video"],
}

_PLATFORM_CHARS = {
    "linkedin":       3000,
    "instagram":      2200,
    "blog":           99999,
    "xiaohongshu":    1000,
    "wechat_moments": 1000,
}


class HistoryItem(BaseModel):
    brief: str
    copy:  str

class CreateAssistedRequest(BaseModel):
    platform:        str
    brief:           str
    image_base64:    Optional[str] = None
    image_mime_type: Optional[str] = None
    history:         list[HistoryItem] = []


class FormatRecommendation(BaseModel):
    format:       str
    rationale:    str
    slides:       Optional[int] = None
    alternatives: list[str]


class ImageSuggestion(BaseModel):
    description: str
    style:       str
    mood:        str


class CreateAssistedResponse(BaseModel):
    copy:                   str
    format_recommendation:  FormatRecommendation
    visual_brief:           str
    image_suggestions:      list[ImageSuggestion]
    char_count:             int
    word_count:             int
    platform:               str


def _load_brand_context() -> str:
    try:
        return _BRAND_CONTEXT_PATH.read_text("utf-8").strip()
    except FileNotFoundError:
        return ""


def _build_system_prompt(platform: str, has_image: bool, history: list[HistoryItem] | None = None) -> str:
    brand_ctx = _load_brand_context()
    formats   = _PLATFORM_FORMATS.get(platform, ["single_image", "carousel", "video"])
    char_limit = _PLATFORM_CHARS.get(platform, 2000)

    brand_section = f"\n\n## Brand context\n{brand_ctx}" if brand_ctx else ""

    history_section = ""
    if history:
        items = "\n\n".join(
            f"Brief: {h.brief}\nCopy: {h.copy[:200]}{'...' if len(h.copy) > 200 else ''}"
            for h in history[-3:]
        )
        history_section = f"\n\n## Recent posts (avoid repeating these topics or angles)\n{items}"

    image_instruction = (
        "An image has been uploaded. Analyse it and reference it in the copy and visual brief."
        if has_image else
        "No image was uploaded. Provide 3 image suggestions in `image_suggestions`."
    )

    return f"""You are a senior social media content creator for Hexa Hub.{brand_section}{history_section}

Platform: {platform}
Character limit: {char_limit}
Available formats: {", ".join(formats)}

{image_instruction}

Your ENTIRE response must be a single valid JSON object starting with {{ and ending with }}.
No preamble, no explanation, no markdown fences.

Required structure:
{{
  "copy": "<the full post copy, platform-appropriate length>",
  "format_recommendation": {{
    "format": "<one of: {", ".join(formats)}>",
    "rationale": "<1-2 sentences explaining why this format suits the content>",
    "slides": <integer if carousel, else null>,
    "alternatives": ["<other viable formats>"]
  }},
  "visual_brief": "<detailed art direction: dimensions, style, colours, mood, key elements>",
  "image_suggestions": [
    {{"description": "<what to photograph/create>", "style": "<visual style>", "mood": "<mood/feeling>"}},
    {{"description": "...", "style": "...", "mood": "..."}},
    {{"description": "...", "style": "...", "mood": "..."}}
  ]
}}

Rules:
- copy must be ready to publish — no placeholders
- Stay within the character limit
- image_suggestions should be empty array [] if an image was provided
- format_recommendation.slides is only set for carousel format"""


async def _call_llm(
    system_prompt: str,
    brief:         str,
    image_base64:  Optional[str],
    image_mime:    Optional[str],
) -> dict:
    import anthropic
    from backend.utils.json_utils import extract_json

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    if image_base64:
        brief_text = f"Brief: {brief}" if brief.strip() else "No brief provided — analyse the image and create a post based on what you see."
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_mime or "image/jpeg",
                    "data": image_base64,
                },
            },
            {"type": "text", "text": f"{brief_text}\n\nGenerate the post now."},
        ]
    else:
        content = f"Brief: {brief}\n\nGenerate the post now."

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0.75,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
    )

    raw = extract_json(message.content[0].text)
    return raw


def _fallback_response(platform: str, brief: str) -> CreateAssistedResponse:
    copy = (
        f"Hexa Hub helps cross-border brands enter the Australian market faster.\n\n"
        f"Topic: {brief[:100]}\n\n"
        f"[Connect your Anthropic API key to generate real content]"
    )
    return CreateAssistedResponse(
        copy=copy,
        format_recommendation=FormatRecommendation(
            format="single_image",
            rationale="Default format — connect API key for AI recommendation.",
            slides=None,
            alternatives=["carousel"],
        ),
        visual_brief="Clean branded image with Hexa green (#7F8B2F) accent on white background.",
        image_suggestions=[
            ImageSuggestion(description="Professional office setting", style="Corporate clean", mood="Confident"),
            ImageSuggestion(description="Product flat-lay on white", style="Minimalist", mood="Premium"),
            ImageSuggestion(description="Team collaboration shot", style="Documentary", mood="Authentic"),
        ],
        char_count=len(copy),
        word_count=len(copy.split()),
        platform=platform,
    )


@router.post("/assisted", response_model=CreateAssistedResponse,
             summary="AI-assisted post creation with optional image upload")
async def create_assisted(
    body: CreateAssistedRequest,
    _:    User = Depends(get_current_user),
) -> CreateAssistedResponse:
    valid_platforms = set(_PLATFORM_FORMATS.keys())
    if body.platform not in valid_platforms:
        raise HTTPException(422, f"Unknown platform: {body.platform}. Valid: {sorted(valid_platforms)}")

    if not settings.ANTHROPIC_API_KEY:
        return _fallback_response(body.platform, body.brief)

    has_image     = bool(body.image_base64)
    system_prompt = _build_system_prompt(body.platform, has_image, body.history or None)

    try:
        raw = await _call_llm(system_prompt, body.brief, body.image_base64, body.image_mime_type)
    except Exception as exc:
        log.error("create_assisted_llm_failed", error=str(exc))
        return _fallback_response(body.platform, body.brief)

    fmt = raw.get("format_recommendation", {})
    suggestions = [
        ImageSuggestion(**s) for s in raw.get("image_suggestions", [])
    ] if not has_image else []

    copy = raw.get("copy", "")
    return CreateAssistedResponse(
        copy=copy,
        format_recommendation=FormatRecommendation(
            format=fmt.get("format", "single_image"),
            rationale=fmt.get("rationale", ""),
            slides=fmt.get("slides"),
            alternatives=fmt.get("alternatives", []),
        ),
        visual_brief=raw.get("visual_brief", ""),
        image_suggestions=suggestions,
        char_count=len(copy),
        word_count=len(copy.split()),
        platform=body.platform,
    )
