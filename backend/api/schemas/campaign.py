from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    name:       str            = Field(min_length=2, max_length=255)
    brief:      str            = Field(min_length=20)
    objective:  str            = Field(min_length=10)
    kpis:       dict[str, Any] = Field(default_factory=dict)
    start_date: date
    end_date:   date
    platforms:  list[str]      = Field(min_length=1)


class CampaignUpdate(BaseModel):
    name:       Optional[str]  = None
    status:     Optional[str]  = None
    start_date: Optional[date] = None
    end_date:   Optional[date] = None
    kpis:       Optional[dict[str, Any]] = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         uuid.UUID
    name:       str
    brief:      str
    objective:  str
    kpis:       dict[str, Any]
    start_date: date
    end_date:   date
    status:     str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class PostSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              uuid.UUID
    platform:        str
    pillar_id:       Optional[uuid.UUID]
    scheduled_at:    Optional[datetime]
    status:          str
    copy:            Optional[str]
    visual_url:      Optional[str]
    approval_status: str
    metadata_json:   dict[str, Any]


class CampaignCalendarResponse(BaseModel):
    campaign: CampaignResponse
    posts:    list[PostSlotResponse]
    total:    int
