"""
Token estimation for all agent system prompts.

Run from the backend/ directory:
    python scripts/estimate_tokens.py

Uses a 4-chars/token heuristic. This is deliberately rough — the real count
varies by model tokeniser. Use this for planning (flag agents near context
limits) not for billing estimates.

30k token flag: Anthropic's Claude context window is 200k tokens so 30k for
a system prompt is not a hard limit, but it is expensive at scale. The proper
fix is prompt caching (reduces repeat costs to ~10%) — a future optimisation.
"""
from __future__ import annotations

import sys
import os

# Allow running from backend/ without installing the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.strategy import StrategyAgent
from backend.agents.calendar import CalendarAgent
from backend.agents.copy.linkedin import LinkedInCopyAgent
from backend.agents.copy.blog import BlogCopyAgent
from backend.agents.copy.instagram import InstagramCopyAgent
from backend.agents.copy.xiaohongshu import XiaohongshuCopyAgent
from backend.agents.copy.wechat import WeChatMomentsAgent
from backend.agents.compliance import ComplianceAgent
from backend.skills.loader import skill_loader

_AGENT_PROMPT_MAP = [
    (StrategyAgent,        "strategy"),
    (CalendarAgent,        "calendar"),
    (LinkedInCopyAgent,    "copy_linkedin"),
    (BlogCopyAgent,        "copy_blog"),
    (InstagramCopyAgent,   "copy_instagram"),
    (XiaohongshuCopyAgent, "copy_xiaohongshu"),
    (WeChatMomentsAgent,   "copy_wechat"),
    (ComplianceAgent,      "compliance"),
]

_WARN_TOKENS  = 30_000
_CHARS_PER_TOKEN = 4


def estimate() -> None:
    print("\nSystem prompt token estimates (4 chars/token heuristic)\n" + "=" * 56)
    flagged: list[tuple[str, int]] = []

    for AgentClass, prompt_name in _AGENT_PROMPT_MAP:
        agent  = AgentClass()
        tokens = agent.estimate_prompt_tokens(prompt_name)

        # Breakdown: skill chars vs agent prompt chars
        from backend.prompts import load_prompt
        try:
            agent_prompt_chars = len(load_prompt(prompt_name))
        except FileNotFoundError:
            agent_prompt_chars = 0

        skill_chars = sum(
            len(skill_loader.load(s))
            for s in agent.required_skills
            if _skill_exists(s)
        )
        total_chars = agent_prompt_chars + skill_chars

        flag = " ⚠️  OVER 30k" if tokens > _WARN_TOKENS else ""
        print(
            f"  {AgentClass.__name__:<26}  ~{tokens:>6,} tokens"
            f"  (skills: {skill_chars // _CHARS_PER_TOKEN:,}t"
            f"  + prompt: {agent_prompt_chars // _CHARS_PER_TOKEN:,}t)"
            f"{flag}"
        )
        if tokens > _WARN_TOKENS:
            flagged.append((AgentClass.__name__, tokens))

    print()
    if flagged:
        print("⚠️  Agents over 30k tokens:")
        for name, t in flagged:
            print(f"   {name}: ~{t:,} tokens")
        print(
            "\n   Recommended fix (future task): Anthropic prompt caching.\n"
            "   Cached prefixes cost ~10% of regular input tokens after the\n"
            "   first request, making large skill blocks much cheaper at scale."
        )
    else:
        print("✅ All agents within 30k token guideline.")

    print()


def _skill_exists(name: str) -> bool:
    try:
        skill_loader.load(name)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    estimate()
