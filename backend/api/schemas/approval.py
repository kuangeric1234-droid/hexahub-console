from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ApprovalQueueItem(BaseModel):
    post_id:       uuid.UUID
    campaign_id:   uuid.UUID
    campaign_name: str
    platform:      str
    copy:          Optional[str]
    visual_url:    Optional[str]
    scheduled_at:  Optional[datetime]
    created_at:    Optional[datetime]


class ApprovalQueueCount(BaseModel):
    count: int


class ApprovalHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:        uuid.UUID
    post_id:   uuid.UUID
    reviewer:  str
    decision:  str
    feedback:  Optional[str]
    timestamp: Optional[datetime]


class BatchApproveRequest(BaseModel):
    post_ids: list[uuid.UUID]
    feedback: Optional[str] = None


class BatchApproveResult(BaseModel):
    approved: list[uuid.UUID]
    failed:   list[dict]   # [{post_id, reason}]
