from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from backend.db.models import Platform


class CopyInput(BaseModel):
    post_id:            UUID
    campaign_id:        UUID
    platform:           Platform
    pillar_name:        str
    working_title:      str
    content_brief:      str
    target_audience:    str = "Cross-border e-commerce brands entering AU"
    campaign_context:   str = ""  # optional campaign-level context injected by orchestrator


class CopyOutput(BaseModel):
    post_id:    UUID
    platform:   Platform
    copy:       str
    char_count: int
    word_count: int
    metadata:   dict[str, Any] = {}   # platform-specific extras (hashtags, headings …)
    warnings:   list[str]      = []   # non-fatal limit/style issues
