from __future__ import annotations

from backend.agents.copy.base import BaseCopyAgent
from backend.agents.schemas.copy import CopyInput, CopyOutput
from backend.db.models import Platform
from backend.llm.client import LLMProvider

_MAX_CHARS = 150


class WeChatMomentsAgent(BaseCopyAgent):
    """
    Ultra-short conversational copy for WeChat Moments (朋友圈).

    Hard cap: 150 characters. If LLM returns longer copy, it is truncated
    at the last complete sentence within the limit and a warning is added.

    Western marketing skills are intentionally excluded — see XiaohongshuCopyAgent
    docstring for the cultural rationale.
    """
    agent_name       = "wechat_moments_agent"
    platform         = Platform.wechat_moments
    default_provider = LLMProvider.ANTHROPIC
    max_chars        = _MAX_CHARS
    required_skills  = [
        "wechat-moments-content",  # custom placeholder in backend/skills/custom/
    ]

    def _parse_output(self, content: str, inp: CopyInput) -> CopyOutput:
        copy     = content.strip()
        warnings = []

        if len(copy) > _MAX_CHARS:
            warnings.append(
                f"Copy was {len(copy)} chars and has been hard-truncated to {_MAX_CHARS}"
            )
            truncated = copy[:_MAX_CHARS]
            for punct in ("。", "！", "？", "…", ".", "!", "?"):
                idx = truncated.rfind(punct)
                if idx > _MAX_CHARS // 2:
                    truncated = truncated[: idx + 1]
                    break
            copy = truncated

        return CopyOutput(
            post_id=inp.post_id,
            platform=inp.platform,
            copy=copy,
            char_count=len(copy),
            word_count=len(copy.split()),
            metadata={
                "language":   "zh",
                "char_limit": _MAX_CHARS,
            },
            warnings=warnings,
        )
