from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AgentLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          uuid.UUID
    agent_name:  str
    task:        str
    input_json:  dict[str, Any]
    output_json: Optional[dict[str, Any]]
    status:      str
    duration_ms: Optional[int]
    timestamp:   Optional[datetime]
