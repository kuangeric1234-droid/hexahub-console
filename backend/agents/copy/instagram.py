from __future__ import annotations

import re

from backend.agents.copy.base import BaseCopyAgent
from backend.agents.schemas.copy import CopyInput, CopyOutput
from backend.db.models import Platform
from backend.llm.client import LLMProvider

_TARGET_HASHTAGS = (5, 10)


class InstagramCopyAgent(BaseCopyAgent):
    agent_name       = "instagram_copy_agent"
    platform         = Platform.instagram
    default_provider = LLMProvider.ANTHROPIC
    max_chars        = 2200
    required_skills  = [
        "copywriting",
        "social-content",
        "ad-creative",
    ]

    def _parse_output(self, content: str, inp: CopyInput) -> CopyOutput:
        copy       = content.strip()
        char_count = len(copy)
        word_count = len(copy.split())
        warnings   = self._limit_warnings(char_count, word_count)

        hashtags = re.findall(r"#[\w一-鿿]+", copy)

        lo, hi = _TARGET_HASHTAGS
        if len(hashtags) < lo:
            warnings.append(f"Only {len(hashtags)} hashtags found; target is {lo}–{hi}")
        elif len(hashtags) > hi:
            warnings.append(f"{len(hashtags)} hashtags found; target is {lo}–{hi}")

        return CopyOutput(
            post_id=inp.post_id,
            platform=inp.platform,
            copy=copy,
            char_count=char_count,
            word_count=word_count,
            metadata={
                "hashtags":      hashtags,
                "hashtag_count": len(hashtags),
            },
            warnings=warnings,
        )
