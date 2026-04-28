"""
Utility tools router — only the repurpose workflow endpoint remains here.
Compliance and webhook endpoints have moved to routes/compliance.py
and routes/webhooks.py respectively.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_current_user
from backend.db.models import User
from backend.orchestrator.repurpose_workflow import RepurposeInput, RepurposeOutput, repurpose

router = APIRouter(tags=["tools"])


@router.post(
    "/repurpose",
    response_model=RepurposeOutput,
    summary="Repurpose content across platforms in parallel",
)
async def repurpose_content(
    body: RepurposeInput,
    _:    User = Depends(get_current_user),
) -> RepurposeOutput:
    return await repurpose(body)
