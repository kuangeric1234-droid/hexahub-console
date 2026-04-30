"""
Brand / product context routes.

GET  /brand/context          current product marketing context
PUT  /brand/context          update context (clears skill cache)
GET  /brand/skills           list available marketing skills
GET  /brand/skills/{name}    full markdown content of one skill (admin)
POST /brand/scan             analyse pasted posts → content DNA
GET  /brand/dna              retrieve stored content DNA
PUT  /brand/dna              save content DNA
"""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_current_admin, get_current_user
from backend.db.models import User
from backend.skills.loader import skill_loader

log    = structlog.get_logger()
router = APIRouter(prefix="/brand", tags=["brand"])

# Brand context stored as a simple markdown file alongside the prompts
_CONTEXT_PATH = Path(__file__).parent.parent.parent / "prompts" / "brand_context.md"
_DNA_PATH     = Path(__file__).parent.parent.parent / "prompts" / "brand_dna.md"


class BrandContextResponse(BaseModel):
    content:  str
    source:   str


class BrandContextUpdate(BaseModel):
    content: str


class SkillListResponse(BaseModel):
    external: list[str]
    custom:   list[str]


class PlatformPosts(BaseModel):
    platform: str
    posts:    list[str]


class ScanRequest(BaseModel):
    samples: list[PlatformPosts]


class ScanResponse(BaseModel):
    dna:    str
    saved:  bool


class DnaResponse(BaseModel):
    content: str
    exists:  bool


@router.get("/context", response_model=BrandContextResponse, summary="Product marketing context")
async def get_context(_: User = Depends(get_current_user)) -> BrandContextResponse:
    if _CONTEXT_PATH.exists():
        return BrandContextResponse(content=_CONTEXT_PATH.read_text("utf-8"), source=str(_CONTEXT_PATH))
    return BrandContextResponse(content="No brand context found.", source="default")


@router.put("/context", response_model=BrandContextResponse, summary="Update brand context")
async def update_context(
    body: BrandContextUpdate,
    _:    User = Depends(get_current_user),
) -> BrandContextResponse:
    _CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONTEXT_PATH.write_text(body.content, encoding="utf-8")
    skill_loader.clear_cache()
    log.info("brand_context_updated", by=_.email)
    return BrandContextResponse(content=body.content, source=str(_CONTEXT_PATH))


@router.get("/skills", response_model=SkillListResponse, summary="List available marketing skills")
async def list_skills(_: User = Depends(get_current_user)) -> SkillListResponse:
    available = skill_loader.list_available()
    return SkillListResponse(**available)


@router.get("/skills/{skill_name}", summary="Skill content (admin only)")
async def get_skill(
    skill_name: str,
    _admin:     User = Depends(get_current_admin),
) -> dict:
    try:
        content = skill_loader.load(skill_name)
        return {"skill_name": skill_name, "content": content}
    except Exception as exc:
        raise HTTPException(404, f"Skill '{skill_name}' not found: {exc}")


# ── GET /brand/dna ─────────────────────────────────────────────────────────────

@router.get("/dna", response_model=DnaResponse, summary="Get stored content DNA")
async def get_dna(_: User = Depends(get_current_user)) -> DnaResponse:
    if _DNA_PATH.exists():
        return DnaResponse(content=_DNA_PATH.read_text("utf-8"), exists=True)
    return DnaResponse(content="", exists=False)


# ── PUT /brand/dna ─────────────────────────────────────────────────────────────

@router.put("/dna", response_model=DnaResponse, summary="Save content DNA")
async def update_dna(
    body: BrandContextUpdate,
    _:    User = Depends(get_current_user),
) -> DnaResponse:
    _DNA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DNA_PATH.write_text(body.content, encoding="utf-8")
    log.info("brand_dna_updated", by=_.email)
    return DnaResponse(content=body.content, exists=True)


# ── POST /brand/scan ───────────────────────────────────────────────────────────

@router.post("/scan", response_model=ScanResponse, summary="Analyse pasted posts → content DNA")
async def scan_content(
    body: ScanRequest,
    _:    User = Depends(get_current_user),
) -> ScanResponse:
    from backend.config import settings
    import anthropic

    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    if not body.samples:
        raise HTTPException(422, "No post samples provided")

    # Build the posts section
    posts_text = ""
    for sample in body.samples:
        if not sample.posts:
            continue
        posts_text += f"\n\n### {sample.platform.upper()}\n"
        for i, post in enumerate(sample.posts, 1):
            posts_text += f"\n**Post {i}:**\n{post.strip()}\n"

    if not posts_text.strip():
        raise HTTPException(422, "No post content provided")

    brand_ctx = _CONTEXT_PATH.read_text("utf-8") if _CONTEXT_PATH.exists() else ""

    system = f"""You are a brand strategist analysing existing social media content to extract a content DNA profile.
{"Brand context: " + brand_ctx[:2000] if brand_ctx else ""}

Analyse the provided posts and produce a detailed Content DNA profile covering:
1. **Voice & Tone** — how do they write? formal/casual, confident/humble, direct/storytelling?
2. **Recurring Themes** — what topics come up most? what angles do they take?
3. **Content Structure** — how do posts open? how do they close? typical length?
4. **Language Patterns** — specific words, phrases, sentence structures they favour
5. **Hashtag Style** — how many, what type, branded vs generic?
6. **What to Avoid** — topics or styles not yet covered that could be gaps
7. **Recommendations** — 3 specific suggestions to improve future content

Write the profile in clear markdown. Be specific — quote actual phrases from the posts where relevant."""

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        temperature=0.3,
        system=system,
        messages=[{"role": "user", "content": f"Here are the posts to analyse:{posts_text}\n\nGenerate the Content DNA profile."}],
    )

    dna = message.content[0].text.strip()

    # Auto-save
    _DNA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DNA_PATH.write_text(dna, encoding="utf-8")
    log.info("brand_dna_scanned", by=_.email, platforms=[s.platform for s in body.samples])

    return ScanResponse(dna=dna, saved=True)
