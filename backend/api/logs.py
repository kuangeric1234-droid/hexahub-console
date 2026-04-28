"""
GET /agent-logs — filterable agent activity timeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.db.models import AgentLog, AgentLogStatus

router = APIRouter(prefix="/agent-logs", tags=["agent-logs"])


class AgentLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          uuid.UUID
    agent_name:  str
    task:        str
    input_json:  dict[str, Any]
    output_json: Optional[dict[str, Any]]
    status:      str
    duration_ms: Optional[int]
    timestamp:   Optional[datetime]


@router.get("", response_model=list[AgentLogResponse], summary="Agent activity log")
async def list_agent_logs(
    agent_name: Optional[str] = Query(default=None, description="Filter by agent name"),
    status:     Optional[str] = Query(default=None, description="running | success | failed"),
    from_date:  Optional[datetime] = Query(default=None, description="ISO 8601"),
    to_date:    Optional[datetime] = Query(default=None, description="ISO 8601"),
    skip:       int = Query(default=0,  ge=0),
    limit:      int = Query(default=50, ge=1, le=500),
    db:         AsyncSession = Depends(get_db),
    _:          str          = Depends(get_current_user),
) -> list[AgentLogResponse]:
    """
    Returns agent execution records, most-recent first.

    Useful for debugging generation quality issues and monitoring costs.
    Each record includes `input_json.skills_loaded` showing which skills
    were injected for that run.
    """
    q = select(AgentLog).order_by(AgentLog.timestamp.desc()).offset(skip).limit(limit)

    if agent_name:
        q = q.where(AgentLog.agent_name == agent_name)

    if status:
        try:
            q = q.where(AgentLog.status == AgentLogStatus(status))
        except ValueError:
            pass

    if from_date:
        q = q.where(AgentLog.timestamp >= from_date)

    if to_date:
        q = q.where(AgentLog.timestamp <= to_date)

    result = await db.execute(q)
    return [AgentLogResponse.model_validate(row) for row in result.scalars().all()]
