from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from backend.db.models import Platform


class VisualInput(BaseModel):
    post_id:        UUID
    platform:       Platform
    copy:           str
    pillar_name:    str
    content_brief:  str
    generate_image: bool = False  # if True, call image provider; False → brief only


class VisualBrief(BaseModel):
    description:  str   # what's in the image — subjects, setting, action
    style_notes:  str   # colours, lighting, composition, mood
    text_overlay: str   # text overlaid on the image; empty string if none
    dimensions:   str   # e.g. "1080x1080"
    alt_text:     str   # accessibility description


class VisualOutput(BaseModel):
    post_id:       UUID
    visual_brief:  VisualBrief
    image_url:     Optional[str] = None   # None when generation is skipped/stubbed
    provider_used: Optional[str] = None
