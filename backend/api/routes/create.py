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
_BRAND_DNA_PATH     = Path(__file__).parent.parent.parent / "prompts" / "brand_dna.md"

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


def _load_brand_dna() -> str:
    try:
        return _BRAND_DNA_PATH.read_text("utf-8").strip()
    except FileNotFoundError:
        return ""


def _build_system_prompt(platform: str, has_image: bool, history: list[HistoryItem] | None = None) -> str:
    brand_ctx = _load_brand_context()
    brand_dna = _load_brand_dna()
    formats   = _PLATFORM_FORMATS.get(platform, ["single_image", "carousel", "video"])
    char_limit = _PLATFORM_CHARS.get(platform, 2000)

    brand_section = f"\n\n## Brand context\n{brand_ctx}" if brand_ctx else ""
    dna_section   = f"\n\n## Content DNA (your existing style — match this voice)\n{brand_dna}" if brand_dna else ""

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

    return f"""You are a senior social media content creator for Hexa Hub.{brand_section}{dna_section}{history_section}

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


# ── POST /create/generate-image ───────────────────────────────────────────────

_PLATFORM_SIZE: dict[str, str] = {
    "instagram":      "1024x1024",
    "facebook":       "1024x1024",
    "linkedin":       "1024x1024",
    "xiaohongshu":    "1024x1792",
    "wechat_moments": "1024x1024",
    "blog":           "1792x1024",
}

_VISION_SYSTEM = """You are a creative director for Hexa Hub, a Melbourne business infrastructure platform.
Analyse the reference image and the user's instructions, then write a precise DALL-E 3 prompt.

Brand aesthetics: clean, operational, modern, real photography feel. White/black/navy palette.
Location context: Huntingdale, Melbourne warehouse and logistics facility.

Output ONLY the DALL-E 3 prompt — no explanation, no preamble, no quotes. Max 900 characters."""


class GenerateImageRequest(BaseModel):
    instructions:    str
    platform:        str   = "instagram"
    drive_file_id:   Optional[str] = None   # reference image from Drive


class GenerateImageResponse(BaseModel):
    image_url:    str   # MinIO URL of the generated image
    prompt_used:  str   # the DALL-E 3 prompt that was generated


@router.post("/generate-image", response_model=GenerateImageResponse,
             summary="GPT-4 Vision + DALL-E 3 image generation with optional Drive reference")
async def generate_image(
    body: GenerateImageRequest,
    _:    User = Depends(get_current_user),
) -> GenerateImageResponse:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(503, "OPENAI_API_KEY not configured — add it to backend/.env")

    import httpx
    import uuid as _uuid
    from openai import AsyncOpenAI

    openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # ── Step 1: fetch reference image from Drive if provided ──────────────────
    image_b64: Optional[str] = None
    if body.drive_file_id:
        if not settings.GOOGLE_DRIVE_API_KEY:
            raise HTTPException(503, "GOOGLE_DRIVE_API_KEY not configured")
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            dl = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{body.drive_file_id}",
                params={"alt": "media", "key": settings.GOOGLE_DRIVE_API_KEY},
            )
            if dl.status_code != 200:
                raise HTTPException(502, f"Could not fetch Drive image: {dl.text[:200]}")
            image_b64 = base64.b64encode(dl.content).decode()

    # ── Step 2: GPT-4 Vision → build DALL-E prompt ────────────────────────────
    user_parts: list = []
    if image_b64:
        user_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "low"},
        })
    user_parts.append({
        "type": "text",
        "text": (
            f"Platform: {body.platform}\n"
            f"User instructions: {body.instructions or 'Create a compelling marketing visual for Hexa Hub.'}\n\n"
            "Write the DALL-E 3 prompt now."
        ),
    })

    vision_resp = await openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _VISION_SYSTEM},
            {"role": "user",   "content": user_parts},
        ],
        max_tokens=400,
        temperature=0.7,
    )
    dalle_prompt = vision_resp.choices[0].message.content or body.instructions

    # ── Step 3: DALL-E 3 generation ───────────────────────────────────────────
    size = _PLATFORM_SIZE.get(body.platform, "1024x1024")
    img_resp = await openai.images.generate(
        model="dall-e-3",
        prompt=dalle_prompt,
        size=size,          # type: ignore[arg-type]
        quality="standard",
        n=1,
    )
    generated_url = img_resp.data[0].url
    if not generated_url:
        raise HTTPException(502, "DALL-E 3 returned no image URL")

    # ── Step 4: download generated image + upload to MinIO (fallback to DALL-E URL) ──
    async with httpx.AsyncClient(timeout=60) as client:
        img_dl = await client.get(generated_url)
        img_dl.raise_for_status()
        img_bytes = img_dl.content

    import boto3 as _boto3
    asset_id = _uuid.uuid4()
    key      = f"assets/{asset_id}.png"
    try:
        s3 = _boto3.client(
            "s3",
            endpoint_url=settings.AWS_ENDPOINT_URL or None,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=img_bytes,
            ContentType="image/png",
        )
        final_url = f"{settings.PUBLIC_BACKEND_URL}/images/{key}"
        log.info("image_generated", asset_id=str(asset_id), platform=body.platform, storage="minio")
    except Exception as exc:
        # MinIO not running — return the DALL-E URL directly (valid ~1 hour)
        log.warning("minio_unavailable_using_dalle_url", error=str(exc))
        final_url = generated_url

    log.info("image_generated_done", platform=body.platform, prompt=dalle_prompt[:80])
    return GenerateImageResponse(image_url=final_url, prompt_used=dalle_prompt)


# ── POST /create/autofill-image ───────────────────────────────────────────────

_AUTOFILL_SYSTEM = """You are a creative director for Hexa Hub, a Melbourne business infrastructure platform.

Given a social media post caption and a list of available image filenames, you must:
1. Pick the SINGLE most relevant filename for this post's visual (or null if none fit)
2. Write detailed DALL-E 3 instructions to generate the ideal image for this post

Brand aesthetics: clean, operational, confident, modern Melbourne warehouse/logistics facility.
Huntingdale location, Australia Post partnerships, cross-border e-commerce brands.

Respond ONLY with valid JSON — no preamble, no explanation:
{
  "selected_file_name": "<exact filename from the list, or null>",
  "instructions": "<detailed DALL-E 3 instructions, 2-4 sentences>"
}"""


class AutofillImageRequest(BaseModel):
    post_copy: str
    platform:  str = "instagram"


class AutofillImageResponse(BaseModel):
    drive_file_id:   Optional[str] = None
    drive_file_name: Optional[str] = None
    thumbnail_url:   Optional[str] = None
    instructions:    str


@router.post("/autofill-image", response_model=AutofillImageResponse,
             summary="Auto-pick Drive image + write DALL-E instructions from post copy")
async def autofill_image(
    body: AutofillImageRequest,
    _:    User = Depends(get_current_user),
) -> AutofillImageResponse:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(503, "OPENAI_API_KEY not configured")
    if not settings.GOOGLE_DRIVE_API_KEY or not settings.GOOGLE_DRIVE_FOLDER_ID:
        raise HTTPException(503, "Google Drive not configured")

    import httpx as _httpx
    from openai import AsyncOpenAI
    from backend.utils.json_utils import extract_json

    # ── Fetch Drive file list ─────────────────────────────────────────────────
    params = {
        "q":        f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed = false",
        "key":      settings.GOOGLE_DRIVE_API_KEY,
        "fields":   "files(id,name,mimeType)",
        "pageSize": 100,
        "orderBy":  "modifiedTime desc",
    }
    async with _httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://www.googleapis.com/drive/v3/files", params=params)

    if resp.status_code != 200:
        raise HTTPException(502, f"Drive API error: {resp.text[:200]}")

    all_files = resp.json().get("files", [])
    # Only include image files for selection
    image_files = [f for f in all_files if f["mimeType"].startswith("image/")]
    file_list   = "\n".join(f["name"] for f in image_files) or "No images found"

    # ── Ask GPT-4 to pick best match + write instructions ─────────────────────
    openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    chat = await openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _AUTOFILL_SYSTEM},
            {"role": "user",   "content": (
                f"Post copy:\n{body.post_copy}\n\n"
                f"Platform: {body.platform}\n\n"
                f"Available image files:\n{file_list}\n\n"
                "Pick the best file and write the DALL-E instructions."
            )},
        ],
        max_tokens=300,
        temperature=0.4,
    )

    raw = extract_json(chat.choices[0].message.content or "{}")

    selected_name: Optional[str] = raw.get("selected_file_name")
    instructions:  str           = raw.get("instructions", body.post_copy[:200])

    # Find matching file ID
    selected_id:   Optional[str] = None
    thumbnail_url: Optional[str] = None
    if selected_name:
        match = next((f for f in image_files if f["name"] == selected_name), None)
        if match:
            selected_id   = match["id"]
            thumbnail_url = f"https://drive.google.com/thumbnail?id={selected_id}&sz=w320"

    log.info("autofill_image", platform=body.platform, selected=selected_name)
    return AutofillImageResponse(
        drive_file_id=selected_id,
        drive_file_name=selected_name,
        thumbnail_url=thumbnail_url,
        instructions=instructions,
    )
