"""
Ad Creative routes.

POST /ad-creative/generate        sync generation (~10-30s)
POST /ad-creative/generate-async  queues job, returns job_id
GET  /ad-creative/jobs/{job_id}   poll job status
GET  /ad-creative/history         past runs
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.ad_creative import AdCreativeAgent
from backend.agents.schemas.ad_creative import AdCreativeInput, AdCreativeOutput
from backend.api.deps import get_current_user, get_db
from backend.api.schemas.ad_creative import (
    AdCreativeRunResponse,
    AsyncJobResponse,
    JobStatusResponse,
)
from backend.db.models import AdCreativeRun, User

log    = structlog.get_logger()
router = APIRouter(prefix="/ad-creative", tags=["ad-creative"])

# In-memory job store — good enough for single-instance. Production: use Redis.
_jobs: dict[str, dict[str, Any]] = {}


# ── POST /ad-creative/generate (sync) ────────────────────────────────────────

@router.post("/generate", response_model=AdCreativeOutput, summary="Generate ad creative (sync)")
async def generate_sync(
    body:         AdCreativeInput,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> AdCreativeOutput:
    output = await AdCreativeAgent()(body, db=db)

    run = AdCreativeRun(
        user_id=current_user.id if hasattr(current_user, "id") else None,
        platform=body.platform,
        input_json=body.model_dump(),
        output_json=output.model_dump(),
    )
    db.add(run)
    await db.flush()
    return output


# ── POST /ad-creative/generate-async ─────────────────────────────────────────

@router.post("/generate-async", response_model=AsyncJobResponse,
             summary="Queue ad creative generation")
async def generate_async(
    body:             AdCreativeInput,
    background_tasks: BackgroundTasks,
    current_user:     User = Depends(get_current_user),
) -> AsyncJobResponse:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "result": None, "error": None}

    async def _run():
        _jobs[job_id]["status"] = "running"
        try:
            from backend.db.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                output = await AdCreativeAgent()(body, db=session)
                run = AdCreativeRun(
                    user_id=current_user.id if hasattr(current_user, "id") else None,
                    platform=body.platform,
                    input_json=body.model_dump(),
                    output_json=output.model_dump(),
                )
                session.add(run)
                await session.commit()
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = output.model_dump()
        except Exception as exc:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"]  = str(exc)
            log.error("ad_creative_job_failed", job_id=job_id, error=str(exc))

    background_tasks.add_task(_run)
    return AsyncJobResponse(job_id=job_id)


# ── GET /ad-creative/jobs/{job_id} ───────────────────────────────────────────

@router.get("/jobs/{job_id}", response_model=JobStatusResponse, summary="Poll async job")
async def job_status(
    job_id: str,
    _:      User = Depends(get_current_user),
) -> JobStatusResponse:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result=job["result"],
        error=job["error"],
    )


# ── GET /ad-creative/history ──────────────────────────────────────────────────

@router.get("/history", response_model=list[AdCreativeRunResponse],
            summary="Past ad creative runs")
async def history(
    platform:    Optional[str]       = Query(default=None),
    campaign_id: Optional[uuid.UUID] = Query(default=None),
    page:        int                  = Query(default=1, ge=1),
    page_size:   int                  = Query(default=20, ge=1, le=100),
    db:          AsyncSession         = Depends(get_db),
    _:           User                 = Depends(get_current_user),
) -> list[AdCreativeRunResponse]:
    q = select(AdCreativeRun).order_by(AdCreativeRun.created_at.desc()) \
        .offset((page - 1) * page_size).limit(page_size)
    if platform:     q = q.where(AdCreativeRun.platform == platform)
    if campaign_id:  q = q.where(AdCreativeRun.campaign_id == campaign_id)
    result = await db.execute(q)
    return [AdCreativeRunResponse.model_validate(r) for r in result.scalars().all()]
