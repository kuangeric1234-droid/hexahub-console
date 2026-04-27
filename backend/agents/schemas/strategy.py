from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from backend.db.models import Platform


class StrategyInput(BaseModel):
    campaign_id: UUID
    name:        str
    brief:       str = Field(min_length=20)
    objective:   str = Field(min_length=10)
    kpis:        dict[str, Any] = Field(default_factory=dict)
    start_date:  date
    end_date:    date
    platforms:   list[Platform] = Field(min_length=1)

    @model_validator(mode="after")
    def dates_are_ordered(self) -> StrategyInput:
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class PillarDef(BaseModel):
    name:        str
    description: str
    weight:      float = Field(ge=0.0, le=1.0)


class PlatformCadence(BaseModel):
    platform:       Platform
    posts_per_week: int  = Field(ge=1, le=21)
    best_days:      list[str]    # e.g. ["Monday", "Thursday"]
    best_time_utc:  str          # e.g. "09:00" — UTC for Western, converted for CN
    tone_notes:     str


class KPITarget(BaseModel):
    metric: str
    target: float
    unit:   str   # "percent" | "count" | "reach"


class StrategyOutput(BaseModel):
    campaign_id: UUID
    pillars:     list[PillarDef]    = Field(min_length=1)
    cadence:     list[PlatformCadence]
    kpi_targets: list[KPITarget]
    rationale:   str

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> StrategyOutput:
        total = sum(p.weight for p in self.pillars)
        if not (0.95 <= total <= 1.05):
            raise ValueError(f"Pillar weights must sum to ~1.0, got {total:.3f}")
        return self
