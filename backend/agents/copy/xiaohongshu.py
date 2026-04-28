from __future__ import annotations

import re

from backend.agents.copy.base import BaseCopyAgent
from backend.agents.schemas.copy import CopyInput, CopyOutput
from backend.db.models import Platform
from backend.llm.client import LLMProvider

_TAG_PATTERN   = re.compile(r"#[一-鿿\w]+")
_CHINESE_CHARS = re.compile(r"[一-鿿]")


class XiaohongshuCopyAgent(BaseCopyAgent):
    """
    种草-style copy for Xiaohongshu (小红书).

    Western marketing skills are intentionally excluded — the patterns
    (种草 culture, 朋友圈 tone, 违禁词 compliance) are culturally distinct
    and Western copywriting skills would produce mismatched output.

    Swap to QWEN or DEEPSEEK provider for higher-quality native Mandarin::

        agent = XiaohongshuCopyAgent(
            llm_client=LLMClient(provider=LLMProvider.QWEN)
        )
    """
    agent_name       = "xiaohongshu_copy_agent"
    platform         = Platform.xiaohongshu
    default_provider = LLMProvider.ANTHROPIC
    required_skills  = [
        "xiaohongshu-content",  # custom placeholder in backend/skills/custom/
    ]

    def _parse_output(self, content: str, inp: CopyInput) -> CopyOutput:
        copy       = content.strip()
        char_count = len(copy)
        word_count = len(copy.split())
        warnings   = self._limit_warnings(char_count, word_count)

        topic_tags   = _TAG_PATTERN.findall(copy)
        chinese_hits = _CHINESE_CHARS.findall(copy)

        if not chinese_hits:
            warnings.append("No Chinese characters found — XHS copy should be in Mandarin")
        if not topic_tags:
            warnings.append("No topic tags (#话题) found — XHS copy should include topic tags")

        return CopyOutput(
            post_id=inp.post_id,
            platform=inp.platform,
            copy=copy,
            char_count=char_count,
            word_count=word_count,
            metadata={
                "topic_tags": topic_tags,
                "language":   "zh",
            },
            warnings=warnings,
        )
