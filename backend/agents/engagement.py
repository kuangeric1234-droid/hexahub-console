"""
EngagementAgent — STUB

Planned: monitor post engagement (comments, shares, DMs), detect sentiment,
flag high-performing posts for repurposing, trigger auto-replies.

Interface defined here so the orchestrator can reference it; implementation
in a future task.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.db.models import Platform
from backend.llm.client import LLMProvider


class EngagementInput(BaseModel):
    post_id:  UUID
    platform: Platform


class EngagementOutput(BaseModel):
    post_id:         UUID
    platform:        Platform
    engagement_data: dict   # placeholder
    action_required: bool   = False
    recommended_action: Optional[str] = None


class EngagementAgent(BaseAgent[EngagementInput, EngagementOutput]):
    agent_name       = "engagement_agent"
    default_provider = LLMProvider.ANTHROPIC

    async def run(
        self,
        input_data: EngagementInput,
        db: Optional[AsyncSession] = None,
    ) -> EngagementOutput:
        raise NotImplementedError(
            "EngagementAgent is not yet implemented. "
            "It will monitor platform APIs for comments, shares, and sentiment."
        )
