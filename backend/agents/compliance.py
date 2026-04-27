"""
ComplianceAgent

Three sequential checks:
  1. Sensitive-word scan  — rule-based, uses DB (falls back to brand forbidden list)
  2. Brand-guideline check — LLM-based
  3. Platform-policy check — LLM-based (combined with #2 in one prompt to save tokens)

Result: ComplianceOutput with passed=True only when no "error"-severity issues exist.

Retry logic (max 2 retries on compliance fail) lives in the LangGraph orchestrator,
not here.  This agent just reports; the orchestrator decides what to do.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import BaseAgent
from backend.agents.schemas.compliance import (
    ComplianceInput,
    ComplianceIssue,
    ComplianceOutput,
)
from backend.llm.client import LLMProvider
from backend.prompts import load_prompt
from backend.utils.json_utils import extract_json

# Hexa HUB brand-forbidden phrases (from Brand Brain §9).
# Used when no DB session is available (tests, standalone runs).
_BRAND_FORBIDDEN: list[tuple[str, str]] = [
    ("game-changing",                    "medium"),
    ("revolutionary",                    "medium"),
    ("disruptive",                       "medium"),
    ("co-working space",                 "high"),
    ("shared office",                    "high"),
    ("hot desk",                         "high"),
    ("take your business to the next level", "high"),
    ("synergy",                          "medium"),
    ("cutting-edge",                     "medium"),
    ("all-in-one",                       "high"),
    ("unlock your potential",            "high"),
    ("dream big",                        "high"),
    ("best-in-class",                    "medium"),
    ("world-class",                      "medium"),
]

_HIGH_SEVERITIES = {"high", "critical"}


class ComplianceAgent(BaseAgent[ComplianceInput, ComplianceOutput]):
    agent_name       = "compliance_agent"
    default_provider = LLMProvider.ANTHROPIC

    async def run(
        self,
        input_data: ComplianceInput,
        db:         Optional[AsyncSession] = None,
    ) -> ComplianceOutput:
        issues: list[ComplianceIssue] = []

        # ── 1. Sensitive-word scan (rule-based) ───────────────────────────────
        word_list = await self._load_sensitive_words(db)
        copy_lower = input_data.copy.lower()

        for word, severity in word_list:
            if word.lower() in copy_lower:
                issues.append(ComplianceIssue(
                    severity    = "error" if severity in _HIGH_SEVERITIES else "warning",
                    category    = "sensitive_word",
                    description = f"Contains forbidden phrase: '{word}'",
                    suggestion  = f"Remove or replace '{word}' with an approved alternative",
                ))

        # ── 2 + 3. LLM brand-guideline + platform-policy check ────────────────
        issues.extend(await self._llm_check(input_data))

        passed = not any(i.severity == "error" for i in issues)
        return ComplianceOutput(
            post_id    = input_data.post_id,
            passed     = passed,
            issues     = issues,
            checked_at = datetime.now(timezone.utc),
        )

    # ── private ───────────────────────────────────────────────────────────────

    async def _load_sensitive_words(
        self, db: Optional[AsyncSession]
    ) -> list[tuple[str, str]]:
        """Return (word, severity) tuples from DB, or fall back to brand forbidden list."""
        if db is not None:
            from sqlalchemy import select
            from backend.db.models import SensitiveWord

            result = await db.execute(select(SensitiveWord))
            rows   = result.scalars().all()
            return [(r.word, r.severity.value) for r in rows]

        return _BRAND_FORBIDDEN

    async def _llm_check(self, input_data: ComplianceInput) -> list[ComplianceIssue]:
        system_prompt = load_prompt("compliance")
        user_prompt   = (
            f"Platform: {input_data.platform.value}\n\n"
            f"Copy to review:\n{input_data.copy}\n\n"
            "Return the compliance JSON now."
        )

        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.2,  # low temp for deterministic rule application
        )

        try:
            raw    = extract_json(response.content)
            issues = raw.get("issues", [])
            return [ComplianceIssue(**i) for i in issues]
        except Exception:
            # If the LLM returns unparseable output, flag for manual review
            return [
                ComplianceIssue(
                    severity    = "warning",
                    category    = "brand_guideline",
                    description = "Automated compliance check returned unparseable output — manual review recommended",
                    suggestion  = "Review copy manually before approval",
                )
            ]
