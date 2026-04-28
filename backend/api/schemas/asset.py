from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                uuid.UUID
    type:              str
    url:               str
    name:              Optional[str]
    tags:              list[str]
    performance_score: Optional[float]
    created_at:        Optional[datetime]


class AssetUpdate(BaseModel):
    name: Optional[str]      = None
    tags: Optional[list[str]] = None
