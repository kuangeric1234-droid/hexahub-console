"""
AdCreativeAgent

Generates paid ad creative variants for a given platform and objective.
Unlike the organic CopyAgents (which produce one polished post), this agent
produces multiple A/B variants that test different psychological angles.

Language-aware skill loading
----------------------------
Western platforms (meta, linkedin, google) → Western marketing skills
Chinese platforms (xiaohongshu, wechat) in zh-CN → Chinese custom skills only

This is handled by overriding _load_skills_context(), which BaseAgent calls
inside _build_system_prompt(). Existing agents are unaffected.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.agents.schemas.ad_creative import (
    AdCreativeInput,
    AdCreativeOutput,
    AdVariant,
)
from backend.llm.client import LLMProvider
from backend.prompts import load_prompt
from backend.skills.loader import skill_loader
from backend.utils.json_utils import extract_json

_WESTERN_SKILLS = [
    "ad-creative",
    "paid-ads",
    "marketing-psychology",
    "copywriting",
]

_PLATFORM_CN_SKILL: dict[str, list[str]] = {
    "xiaohongshu": ["xiaohongshu-content"],
    "wechat":      ["wechat-moments-content"],
}


class AdCreativeAgent(BaseAgent[AdCreativeInput, AdCreativeOutput]):
    agent_name       = "ad_creative_agent"
    default_provider = LLMProvider.ANTHROPIC
    required_skills  = _WESTERN_SKILLS  # default; overridden per-run by _load_skills_context

    # ── language-aware skill selection ────────────────────────────────────────

    def _load_skills_context(self, input_data: Any = None) -> str:
        """
        Select skills based on request language and platform.

        Chinese requests on XHS/WeChat → Chinese custom skills only.
        Everything else → Western skills (ad-creative, paid-ads, etc.).
        """
        if input_data is not None and isinstance(input_data, AdCreativeInput):
            if input_data.language == "zh-CN":
                skills = _PLATFORM_CN_SKILL.get(input_data.platform, [])
                return skill_loader.load_many(skills)
        return skill_loader.load_many(self.required_skills)

    # ── core run ──────────────────────────────────────────────────────────────

    async def run(
        self,
        input_data: AdCreativeInput,
        db: Optional[AsyncSession] = None,
    ) -> AdCreativeOutput:
        # Pass input_data so _build_system_prompt calls _load_skills_context(input_data)
        system_prompt = self._build_system_prompt(load_prompt("ad_creative"), input_data)
        user_prompt   = self._build_user_prompt(input_data)

        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.8,  # creative variance within structure
        )

        raw = extract_json(response.content)
        return self._parse_output(raw, input_data)

    # ── private ───────────────────────────────────────────────────────────────

    def _build_user_prompt(self, inp: AdCreativeInput) -> str:
        parts = [
            f"Platform:          {inp.platform}",
            f"Objective:         {inp.objective}",
            f"Product / offer:   {inp.product_or_offer}",
            f"Target audience:   {inp.audience}",
            f"Key message:       {inp.key_message}",
            f"CTA:               {inp.cta}",
            f"Variants to generate: {inp.variants_count}",
            f"Language:          {inp.language}",
        ]
        if inp.constraints:
            parts.append(f"Constraints:       {inp.constraints}")
        parts.append("\nGenerate the ad creative JSON now.")
        return "\n".join(parts)

    def _parse_output(self, raw: dict, inp: AdCreativeInput) -> AdCreativeOutput:
        variants = [AdVariant(**v) for v in raw.get("variants", [])]

        priority = raw.get("recommended_test_priority", list(range(len(variants))))
        # Clamp indices to valid range
        priority = [i for i in priority if 0 <= i < len(variants)]

        return AdCreativeOutput(
            variants=variants,
            recommended_test_priority=priority,
            targeting_notes=raw.get("targeting_notes", ""),
        )
