from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from backend.db.models import Platform


class PublishInput(BaseModel):
    post_id:      UUID
    campaign_id:  UUID
    platform:     Platform
    copy:         str
    visual_url:   Optional[str]       = None
    scheduled_at: datetime
    metadata:     dict[str, Any]      = {}


class PublishedResult(BaseModel):
    post_id:                UUID
    platform:               Platform
    # published | scheduled | package_generated | not_configured | failed
    status:                 str
    external_id:            Optional[str]  = None   # platform's post/media ID
    published_at:           Optional[datetime] = None
    requires_manual_action: bool           = False
    publishing_package:     Optional[dict] = None   # populated for XHS / WeChat
    error:                  Optional[str]  = None


class PublishOutput(BaseModel):
    post_id:               UUID
    result:                PublishedResult
    requires_manual_action: bool = False
    webhook_sent:          bool  = False
