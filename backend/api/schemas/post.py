from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              uuid.UUID
    campaign_id:     Optional[uuid.UUID]
    platform:        str
    pillar_id:       Optional[uuid.UUID]
    scheduled_at:    Optional[datetime]
    status:          str
    copy:            Optional[str]
    visual_url:      Optional[str]
    approval_status: str
    metadata_json:   dict[str, Any]
    created_at:      Optional[datetime]
    updated_at:      Optional[datetime]


class PostUpdate(BaseModel):
    copy:          Optional[str]            = None
    visual_url:    Optional[str]            = None
    scheduled_at:  Optional[datetime]       = None
    metadata_json: Optional[dict[str, Any]] = None


class PostVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:             uuid.UUID
    post_id:        uuid.UUID
    version_number: int
    copy:           Optional[str]
    visual_url:     Optional[str]
    scheduled_at:   Optional[datetime]
    edited_by:      Optional[str]
    created_at:     Optional[datetime]


class RegenerateCopyRequest(BaseModel):
    override_prompt: Optional[str] = None


class ApproveRequest(BaseModel):
    feedback: Optional[str] = None


class RejectRequest(BaseModel):
    feedback: str
