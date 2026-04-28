from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ComplianceCheckRequest(BaseModel):
    text:      str
    languages: list[str] = ["zh-CN"]


class ComplianceFlag(BaseModel):
    word:     str
    severity: str
    category: str
    position: int
    length:   int


class ComplianceCheckResult(BaseModel):
    passed:      bool
    flags:       list[ComplianceFlag]
    suggestions: list[str]


class SensitiveWordCreate(BaseModel):
    word:     str
    language: str = "zh-CN"
    severity: str = "medium"
    category: Optional[str] = None


class SensitiveWordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:         uuid.UUID
    word:       str
    language:   str
    severity:   str
    category:   Optional[str]
    created_at: Optional[datetime]
