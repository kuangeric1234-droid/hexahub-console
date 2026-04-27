from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

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
    holiday_notes:      list[str]       # e.g. "618 festival: boost XHS volume Jun 10–18"

    @model_validator(mode="after")
    def totals_are_consistent(self) -> CalendarOutput:
        if self.total_posts != len(self.slots):
            raise ValueError("total_posts must equal len(slots)")
        return self
