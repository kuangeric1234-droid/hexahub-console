from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AdCreativeInput(BaseModel):
    platform:         Literal["meta", "linkedin", "xiaohongshu", "wechat", "google"]
    objective:        Literal["awareness", "traffic", "leads", "conversions", "app_installs"]
    product_or_offer: str
    audience:         str
    key_message:      str
    cta:              str
    variants_count:   int                    = Field(default=3, ge=1, le=5)
    language:         Literal["en", "zh-CN"] = "en"
    constraints:      Optional[str]          = None  # things to avoid


class AdVariant(BaseModel):
    headline:     str
    primary_text: str
    description:  Optional[str] = None   # secondary (LinkedIn / Google)
    cta_button:   str
    visual_brief: str   # fed directly to VisualAgent
    rationale:    str   # the angle being tested — why this variant


class AdCreativeOutput(BaseModel):
    variants:                  list[AdVariant]
    recommended_test_priority: list[int]   # indices ordered best-to-test-first
    targeting_notes:           str         # platform-specific targeting suggestions
