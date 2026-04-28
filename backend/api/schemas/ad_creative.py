from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AdCreativeRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          uuid.UUID
    user_id:     Optional[uuid.UUID]
    campaign_id: Optional[uuid.UUID]
    platform:    str
    input_json:  dict[str, Any]
    output_json: dict[str, Any]
    created_at:  Optional[datetime]


class AsyncJobResponse(BaseModel):
    job_id:  str
    status:  str = "queued"
    message: str = "Job queued. Poll GET /ad-creative/jobs/{job_id} for result."


class JobStatusResponse(BaseModel):
    job_id:  str
    status:  str   # queued | running | done | failed
    result:  Optional[dict[str, Any]] = None
    error:   Optional[str] = None
