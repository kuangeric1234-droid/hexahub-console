"""
StrategyAgent

Input:  StrategyInput  (campaign brief, objective, KPIs, platforms, date range)
Output: StrategyOutput (pillars + cadence + KPI targets)

LLM is given the full brand context via the system prompt and asked to return
a single JSON object. The response is validated against StrategyOutput.
If the pillar weights don't sum to 1.0, we normalise rather than fail.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.agents.schemas.strategy import (
    PillarDef,
    PlatformCadence,
    StrategyInput,
    StrategyOutput,
)
from backend.db.models import Platform
from backend.llm.client import LLMProvider
from backend.prompts import load_prompt
from backend.utils.json_utils import extract_json


class StrategyAgent(BaseAgent[StrategyInput, StrategyOutput]):
    agent_name       = "strategy_agent"
    default_provider = LLMProvider.ANTHROPIC

    def validate(self, input_data: StrategyInput) -> None:
        if not input_data.brief.strip():
            raise ValueError("Campaign brief cannot be empty")
        if not input_data.platforms:
            raise ValueError("At least one platform must be specified")
        if input_data.start_date >= input_data.end_date:
            raise ValueError("start_date must be before end_date")

    async def run(self, input_data: StrategyInput, db: Optional[AsyncSession] = None) -> StrategyOutput:
        system_prompt = load_prompt("strategy")
        user_prompt   = self._build_user_prompt(input_data)

        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.5,  # lower temp for structured/factual output
        )

        raw = extract_json(response.content)
        return self._parse_and_validate(raw, input_data)

    # ── private ───────────────────────────────────────────────────────────────

    def _build_user_prompt(self, inp: StrategyInput) -> str:
        platforms_str = ", ".join(p.value for p in inp.platforms)
        kpis_str      = json.dumps(inp.kpis, indent=2)
        return f"""Campaign brief:

Name:       {inp.name}
Objective:  {inp.objective}
Duration:   {inp.start_date} to {inp.end_date}
Platforms:  {platforms_str}
KPIs:       {kpis_str}

Brief:
{inp.brief}

Generate the content strategy JSON now."""

    def _parse_and_validate(
        self,
        raw:   dict,
        input_data: StrategyInput,
    ) -> StrategyOutput:
        # Normalise pillar weights so they sum to 1.0
        pillars = [PillarDef(**p) for p in raw.get("pillars", [])]
        total   = sum(p.weight for p in pillars)
        if total > 0 and abs(total - 1.0) > 0.01:
            pillars = [
                PillarDef(name=p.name, description=p.description, weight=round(p.weight / total, 4))
                for p in pillars
            ]

        # Filter cadence to requested platforms only
        allowed   = {p.value for p in input_data.platforms}
        cadence   = [
            PlatformCadence(**c)
            for c in raw.get("cadence", [])
            if c.get("platform") in allowed
        ]

        return StrategyOutput(
            campaign_id=input_data.campaign_id,
            pillars=pillars,
            cadence=cadence,
            kpi_targets=raw.get("kpi_targets", []),
            rationale=raw.get("rationale", ""),
        )
