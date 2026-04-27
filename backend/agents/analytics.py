"""
AnalyticsAgent — STUB

Planned: pull reach/engagement/CTR from LinkedIn, Meta, and WordPress;
persist to the metrics table; generate weekly performance summaries.

Interface defined here so the orchestrator can reference it; implementation
in a future task.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.db.models import Platform
from backend.llm.client import LLMProvider


class AnalyticsInput(BaseModel):
    campaign_id: UUID
    start_date:  datetime
    end_date:    datetime
    platforms:   list[Platform]


class AnalyticsOutput(BaseModel):
    campaign_id:     UUID
    period_start:    datetime
    period_end:      datetime
    metrics_by_post: list[dict]   # placeholder
    summary:         str          = ""


class AnalyticsAgent(BaseAgent[AnalyticsInput, AnalyticsOutput]):
    agent_name       = "analytics_agent"
    default_provider = LLMProvider.ANTHROPIC

    async def run(
        self,
        input_data: AnalyticsInput,
        db: Optional[AsyncSession] = None,
    ) -> AnalyticsOutput:
        raise NotImplementedError(
            "AnalyticsAgent is not yet implemented. "
            "It will aggregate metrics from platform APIs and generate reports."
        )
