"""
Agent log routes (admin only).

GET /logs/agent-runs              paginated agent execution log
GET /logs/agent-runs/{log_id}     single run detail
GET /logs/workflow/{thread_id}    all runs for one workflow thread
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_admin, get_db
from backend.api.schemas.log import AgentLogResponse
from backend.db.models import AgentLog, User

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/agent-runs", response_model=list[AgentLogResponse], summary="Agent run log (admin)")
async def list_logs(
    agent_name: Optional[str]      = Query(default=None),
    status:     Optional[str]      = Query(default=None),
    from_date:  Optional[datetime] = Query(default=None),
    to_date:    Optional[datetime] = Query(default=None),
    page:       int                = Query(default=1, ge=1),
    page_size:  int                = Query(default=50, ge=1, le=200),
    db:         AsyncSession       = Depends(get_db),
    _:          User               = Depends(get_current_admin),
) -> list[AgentLogResponse]:
    from backend.db.models import AgentLogStatus
    q = select(AgentLog).order_by(AgentLog.timestamp.desc()) \
        .offset((page - 1) * page_size).limit(page_size)
    if agent_name: q = q.where(AgentLog.agent_name == agent_name)
    if status:
        try:    q = q.where(AgentLog.status == AgentLogStatus(status))
        except ValueError: pass
    if from_date: q = q.where(AgentLog.timestamp >= from_date)
    if to_date:   q = q.where(AgentLog.timestamp <= to_date)
    result = await db.execute(q)
    return [AgentLogResponse.model_validate(r) for r in result.scalars().all()]


@router.get("/agent-runs/{log_id}", response_model=AgentLogResponse, summary="Agent run detail")
async def get_log(
    log_id: uuid.UUID,
    db:     AsyncSession = Depends(get_db),
    _:      User         = Depends(get_current_admin),
) -> AgentLogResponse:
    log_entry = await db.get(AgentLog, log_id)
    if not log_entry:
        raise HTTPException(404, f"Log {log_id} not found")
    return AgentLogResponse.model_validate(log_entry)


@router.get("/workflow/{thread_id}", response_model=list[AgentLogResponse],
            summary="All agent runs for a workflow thread")
async def workflow_logs(
    thread_id: str,
    db:        AsyncSession = Depends(get_db),
    _:         User         = Depends(get_current_admin),
) -> list[AgentLogResponse]:
    # thread_id == str(campaign_id); logs tagged via input_json
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.input_json["campaign_id"].astext == thread_id)
        .order_by(AgentLog.timestamp.asc())
    )
    return [AgentLogResponse.model_validate(r) for r in result.scalars().all()]
