"""
CalendarAgent

Input:  CalendarInput  (StrategyOutput + date range)
Output: CalendarOutput (list of timezone-aware PostSlots)

The LLM receives the full strategy plus holiday context and generates the
complete posting schedule. Returned datetimes are validated for timezone
awareness; slots are flagged as holiday-adjacent using chinese_holidays.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.agents.schemas.calendar import (
    CalendarInput,
    CalendarOutput,
    PostSlot,
)
from backend.db.models import Platform
from backend.llm.client import LLMProvider
from backend.prompts import load_prompt
from backend.utils.chinese_holidays import (
    format_holidays_for_prompt,
    get_holidays_in_range,
    is_holiday_adjacent,
)
from backend.utils.json_utils import extract_json


class CalendarAgent(BaseAgent[CalendarInput, CalendarOutput]):
    agent_name       = "calendar_agent"
    default_provider = LLMProvider.ANTHROPIC

    def validate(self, input_data: CalendarInput) -> None:
        if not input_data.strategy.pillars:
            raise ValueError("Strategy must have at least one pillar")
        if not input_data.strategy.cadence:
            raise ValueError("Strategy must have cadence for at least one platform")
        if input_data.start_date >= input_data.end_date:
            raise ValueError("start_date must be before end_date")

    async def run(self, input_data: CalendarInput, db: Optional[AsyncSession] = None) -> CalendarOutput:
        holidays      = get_holidays_in_range(input_data.start_date, input_data.end_date)
        system_prompt = load_prompt("calendar")
        user_prompt   = self._build_user_prompt(input_data, holidays)

        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=8192,   # calendar output can be large
            temperature=0.4,
        )

        raw = extract_json(response.content)
        return self._parse_and_validate(raw, input_data)

    # ── private ───────────────────────────────────────────────────────────────

    def _build_user_prompt(self, inp: CalendarInput, holidays: list) -> str:
        strategy     = inp.strategy
        pillars_str  = json.dumps(
            [{"name": p.name, "description": p.description, "weight": p.weight}
             for p in strategy.pillars],
            indent=2,
        )
        cadence_str  = json.dumps(
            [{"platform": c.platform.value, "posts_per_week": c.posts_per_week,
              "best_days": c.best_days, "best_time_utc": c.best_time_utc,
              "tone_notes": c.tone_notes}
             for c in strategy.cadence],
            indent=2,
        )
        holidays_str = format_holidays_for_prompt(holidays)

        return f"""Campaign ID: {inp.campaign_id}
Date range: {inp.start_date} to {inp.end_date}

Content pillars:
{pillars_str}

Platform cadence:
{cadence_str}

Chinese holidays / shopping festivals in this period:
{holidays_str}

Generate the complete posting calendar JSON now."""

    def _parse_and_validate(
        self,
        raw:        dict,
        input_data: CalendarInput,
    ) -> CalendarOutput:
        slots: list[PostSlot] = []
        platform_counts: dict[str, int] = {}

        for s in raw.get("slots", []):
            # Ensure campaign_id is set correctly
            s["campaign_id"] = str(input_data.campaign_id)

            # Parse and validate datetime; ensure it is timezone-aware
            scheduled_at = datetime.fromisoformat(s["scheduled_at"])
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            s["scheduled_at"] = scheduled_at

            # Auto-flag holiday adjacency regardless of LLM answer
            s["is_holiday_adjacent"] = is_holiday_adjacent(
                scheduled_at.date(), major_only=False
            )

            slot = PostSlot(**s)
            slots.append(slot)

            platform_counts[slot.platform.value] = (
                platform_counts.get(slot.platform.value, 0) + 1
            )

        return CalendarOutput(
            campaign_id=input_data.campaign_id,
            slots=slots,
            total_posts=len(slots),
            platform_breakdown=platform_counts,
            holiday_notes=raw.get("holiday_notes", []),
        )
