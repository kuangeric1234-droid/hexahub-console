from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel

from backend.db.models import Platform


class ComplianceInput(BaseModel):
    post_id:    UUID
    platform:   Platform
    copy:       str
    visual_url: Optional[str] = None   # reserved for future image-content checks


class ComplianceIssue(BaseModel):
    severity:    Literal["error", "warning"]
    category:    Literal["sensitive_word", "brand_guideline", "platform_policy"]
    description: str
    suggestion:  Optional[str] = None


class ComplianceOutput(BaseModel):
    post_id:    UUID
    passed:     bool               # True only when no "error"-severity issues exist
    issues:     list[ComplianceIssue]
    checked_at: datetime
