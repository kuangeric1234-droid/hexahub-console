"""
Brand / product context routes.

GET  /brand/context          current product marketing context
PUT  /brand/context          update context (clears skill cache)
GET  /brand/skills           list available marketing skills
GET  /brand/skills/{name}    full markdown content of one skill (admin)
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


class BrandContextResponse(BaseModel):
    content:  str
    source:   str


class BrandContextUpdate(BaseModel):
    content: str


class SkillListResponse(BaseModel):
    external: list[str]
    custom:   list[str]


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
