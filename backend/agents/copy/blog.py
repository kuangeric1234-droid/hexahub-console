from __future__ import annotations

import re

from backend.agents.copy.base import BaseCopyAgent
from backend.agents.schemas.copy import CopyInput, CopyOutput
from backend.db.models import Platform
from backend.llm.client import LLMProvider


class BlogCopyAgent(BaseCopyAgent):
    agent_name       = "blog_copy_agent"
    platform         = Platform.blog
    default_provider = LLMProvider.ANTHROPIC
    min_words        = 1200
    max_words        = 2000
    required_skills  = [
        "copywriting",
        "seo-audit",
        "ai-seo",
        "schema-markup",
    ]

    def _parse_output(self, content: str, inp: CopyInput) -> CopyOutput:
        copy       = content.strip()
        char_count = len(copy)
        word_count = len(copy.split())
        warnings   = self._limit_warnings(char_count, word_count)

        headings   = re.findall(r"^#{2,3}\s+(.+)$", copy, re.MULTILINE)
        meta_match = re.search(r"(?i)meta description[:\s]+(.+)", copy)
        meta_desc  = meta_match.group(1).strip() if meta_match else ""

        return CopyOutput(
            post_id=inp.post_id,
            platform=inp.platform,
            copy=copy,
            char_count=char_count,
            word_count=word_count,
            metadata={
                "headings":         headings,
                "meta_description": meta_desc,
            },
            warnings=warnings,
        )
