"""
BaseCopyAgent — shared foundation for all 5 platform copy agents.

Each subclass must set:
  agent_name  (str)
  platform    (Platform)

And optionally override:
  required_skills — list of skill names injected into the system prompt
  max_chars       — emit a warning if copy exceeds this
  max_words       — emit a warning if word count is outside range
  _parse_output() — platform-specific post-processing (hashtag extraction, etc.)

Inherits _build_system_prompt() from BaseAgent. The run() method here calls it
so every copy agent gets skill injection automatically from required_skills.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from backend.agents.base import BaseAgent
from backend.agents.schemas.copy import CopyInput, CopyOutput
from backend.db.models import Platform
from backend.prompts import load_prompt
from backend.utils.utm import inject_utm

_BRAND_CONTEXT_PATH = Path(__file__).parent.parent.parent / "prompts" / "brand_context.md"


def _load_brand_context() -> str:
    try:
        return _BRAND_CONTEXT_PATH.read_text("utf-8").strip()
    except FileNotFoundError:
        return ""

_PROMPT_NAMES: dict[Platform, str] = {
    Platform.linkedin:       "copy_linkedin",
    Platform.blog:           "copy_blog",
    Platform.instagram:      "copy_instagram",
    Platform.xiaohongshu:    "copy_xiaohongshu",
    Platform.wechat_moments: "copy_wechat",
}


class BaseCopyAgent(BaseAgent[CopyInput, CopyOutput]):
    platform:  Platform
    max_chars: Optional[int] = None
    min_words: Optional[int] = None
    max_words: Optional[int] = None

    async def run(self, input_data: CopyInput, db: Optional[AsyncSession] = None) -> CopyOutput:
        # _build_system_prompt injects required_skills before the agent prompt
        system_prompt = self._build_system_prompt(load_prompt(_PROMPT_NAMES[self.platform]))
        user_prompt   = self._build_user_prompt(input_data)

        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=self._max_tokens(),
            temperature=0.8,
        )
        return self._parse_output(response.content, input_data)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _max_tokens(self) -> int:
        if self.max_words:
            return min(self.max_words * 3, 4096)
        return 2048

    def _build_user_prompt(self, inp: CopyInput) -> str:
        parts = []
        brand_ctx = _load_brand_context()
        if brand_ctx:
            parts.append(f"## Brand context\n{brand_ctx}")
        parts += [
            f"Working title:   {inp.working_title}",
            f"Content brief:   {inp.content_brief}",
            f"Content pillar:  {inp.pillar_name}",
            f"Target audience: {inp.target_audience}",
        ]
        if inp.campaign_context:
            parts.append(f"Campaign context: {inp.campaign_context}")
        parts.append("\nWrite the copy now.")
        return "\n\n".join(parts)

    def _parse_output(self, content: str, inp: CopyInput) -> CopyOutput:
        """Base implementation — subclasses override for platform-specific parsing."""
        copy       = inject_utm(content.strip(), inp.platform, inp.campaign_id, inp.post_id)
        char_count = len(copy)
        word_count = len(copy.split())
        warnings   = self._limit_warnings(char_count, word_count)

        return CopyOutput(
            post_id=inp.post_id,
            platform=inp.platform,
            copy=copy,
            char_count=char_count,
            word_count=word_count,
            warnings=warnings,
        )

    def _limit_warnings(self, char_count: int, word_count: int) -> list[str]:
        warnings: list[str] = []
        if self.max_chars and char_count > self.max_chars:
            warnings.append(
                f"Copy is {char_count} chars; platform target is ≤{self.max_chars}"
            )
        if self.min_words and word_count < self.min_words:
            warnings.append(
                f"Copy is {word_count} words; target is {self.min_words}–{self.max_words or '∞'}"
            )
        if self.max_words and word_count > self.max_words:
            warnings.append(
                f"Copy is {word_count} words; target is {self.min_words or 0}–{self.max_words}"
            )
        return warnings
