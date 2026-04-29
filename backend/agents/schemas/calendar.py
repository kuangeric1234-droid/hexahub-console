from __future__ import annotations

from datetime import date, datetime
from typing import Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.agents.schemas.strategy import StrategyOutput
from backend.db.models import Platform


class CalendarInput(BaseModel):
    campaign_id: UUID
    strategy:    StrategyOutput
    start_date:  date
    end_date:    date

    @model_validator(mode="after")
    def dates_are_ordered(self) -> CalendarInput:
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class PostSlot(BaseModel):
    campaign_id:         UUID
    platform:            Platform
    pillar_name:         str
    scheduled_at:        datetime  # always timezone-aware (UTC or Asia/Shanghai)
    working_title:       str
    content_brief:       str
    is_holiday_adjacent: bool = False


class CalendarOutput(BaseModel):
    campaign_id:        UUID
    slots:              list[PostSlot]
    total_posts:        int
    platform_breakdown: dict[str, int]  # platform.value → count
    holiday_notes:      list[str] = []  # e.g. "618 festival: boost XHS volume Jun 10–18"

    @field_validator("holiday_notes", mode="before")
    @classmethod
    def coerce_holiday_notes(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                # LLM sometimes returns {"holiday": "...", "note": "..."} — flatten to string
                parts = [str(val) for val in item.values() if val]
                result.append(" — ".join(parts))
            else:
                result.append(str(item))
        return result

    @model_validator(mode="after")
    def totals_are_consistent(self) -> CalendarOutput:
        if self.total_posts != len(self.slots):
            raise ValueError("total_posts must equal len(slots)")
        return self
