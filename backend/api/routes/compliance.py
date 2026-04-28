"""
Compliance routes.

POST /compliance/check                     instant 违禁词 scan (no LLM, <50ms)
GET  /compliance/sensitive-words           list words (admin/member)
POST /compliance/sensitive-words           add word (admin)
DELETE /compliance/sensitive-words/{id}    remove word (admin)
POST /compliance/run-full-check/{post_id}  full LLM check (async)
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.compliance import quick_compliance
from backend.api.deps import get_current_admin, get_current_user, get_db
from backend.api.schemas.compliance import (
    ComplianceCheckRequest,
    ComplianceCheckResult,
    ComplianceFlag,
    SensitiveWordCreate,
    SensitiveWordResponse,
)
from backend.db.models import SensitiveWord, User, WordSeverity

log    = structlog.get_logger()
router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/check", response_model=ComplianceCheckResult, summary="Fast 违禁词 scan (no LLM)")
async def compliance_check(
    body: ComplianceCheckRequest,
    _:    User = Depends(get_current_user),
) -> ComplianceCheckResult:
    all_flags: list[dict] = []
    suggestions: list[str] = []
    for lang in body.languages:
        result = quick_compliance.check(body.text, lang)
        all_flags.extend(result["flags"])
        suggestions.extend(s for s in result["suggestions"] if s not in suggestions)

    passed = not any(f["severity"] in {"high", "critical"} for f in all_flags)
    flags  = sorted(all_flags, key=lambda f: f["position"])
    return ComplianceCheckResult(
        passed=passed,
        flags=[ComplianceFlag(**f) for f in flags],
        suggestions=suggestions,
    )


@router.get("/sensitive-words", response_model=list[SensitiveWordResponse],
            summary="List sensitive words")
async def list_words(
    language: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db:       AsyncSession = Depends(get_db),
    _:        User         = Depends(get_current_user),
) -> list[SensitiveWordResponse]:
    q = select(SensitiveWord).order_by(SensitiveWord.language, SensitiveWord.word)
    if language: q = q.where(SensitiveWord.language == language)
    if category: q = q.where(SensitiveWord.category == category)
    result = await db.execute(q)
    return [SensitiveWordResponse.model_validate(w) for w in result.scalars().all()]


@router.post("/sensitive-words", response_model=SensitiveWordResponse,
             summary="Add sensitive word (admin)")
async def add_word(
    body:   SensitiveWordCreate,
    db:     AsyncSession = Depends(get_db),
    _admin: User         = Depends(get_current_admin),
) -> SensitiveWordResponse:
    try:
        severity_enum = WordSeverity(body.severity)
    except ValueError:
        raise HTTPException(422, f"Invalid severity: {body.severity}")

    word = SensitiveWord(
        word=body.word, language=body.language,
        severity=severity_enum, category=body.category,
    )
    db.add(word)
    await db.flush()
    quick_compliance.invalidate_cache()
    return SensitiveWordResponse.model_validate(word)


@router.delete("/sensitive-words/{word_id}", summary="Remove sensitive word (admin)")
async def delete_word(
    word_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    _admin:  User         = Depends(get_current_admin),
) -> dict:
    word = await db.get(SensitiveWord, word_id)
    if not word:
        raise HTTPException(404, f"Word {word_id} not found")
    await db.delete(word)
    await db.flush()
    quick_compliance.invalidate_cache()
    return {"deleted": str(word_id)}


@router.post("/run-full-check/{post_id}", response_model=dict,
             summary="Full LLM compliance check (async)")
async def full_check(
    post_id:          uuid.UUID,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    _:                User         = Depends(get_current_user),
) -> dict:
    from backend.db.models import Post
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if not post.copy:
        raise HTTPException(422, "Post has no copy to check")

    async def _run():
        from backend.agents.compliance import ComplianceAgent
        from backend.agents.schemas.compliance import ComplianceInput
        from backend.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            p = await session.get(Post, post_id)
            if not p:
                return
            await ComplianceAgent()(
                ComplianceInput(post_id=post_id, platform=p.platform, copy=p.copy or ""),
                db=session,
            )

    background_tasks.add_task(_run)
    return {"message": "Full compliance check queued", "post_id": str(post_id)}
