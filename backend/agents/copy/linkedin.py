from __future__ import annotations

from backend.agents.copy.base import BaseCopyAgent
from backend.agents.schemas.copy import CopyInput, CopyOutput
from backend.db.models import Platform
from backend.llm.client import LLMProvider


class LinkedInCopyAgent(BaseCopyAgent):
    agent_name       = "linkedin_copy_agent"
    platform         = Platform.linkedin
    default_provider = LLMProvider.ANTHROPIC
    max_chars        = 1300

    def _parse_output(self, content: str, inp: CopyInput) -> CopyOutput:
        copy       = content.strip()
        char_count = len(copy)
        word_count = len(copy.split())
        warnings   = self._limit_warnings(char_count, word_count)

        # Extract the hook line (first non-empty line) for metadata
        lines     = [l for l in copy.splitlines() if l.strip()]
        hook_line = lines[0] if lines else ""

        return CopyOutput(
            post_id=inp.post_id,
            platform=inp.platform,
            copy=copy,
            char_count=char_count,
            word_count=word_count,
            metadata={
                "hook_line":         hook_line,
                "platform_char_limit": self.max_chars,
            },
            warnings=warnings,
        )
