"""
ComplianceAgent + QuickComplianceCheck

ComplianceAgent  — full async agent: word scan + LLM brand/platform check.
                   Used inside the orchestrator workflow.

QuickComplianceCheck — sync, no LLM, for real-time UI feedback (违禁词 tool).
                       Returns word positions for in-browser highlighting.
                       Loads words from DB on first call; caches for 5 min.
"""
from __future__ import annotations

import re
import time
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

_BRAND_FORBIDDEN: list[tuple[str, str]] = [
    ("game-changing",                        "medium"),
    ("revolutionary",                        "medium"),
    ("disruptive",                           "medium"),
    ("co-working space",                     "high"),
    ("shared office",                        "high"),
    ("hot desk",                             "high"),
    ("take your business to the next level", "high"),
    ("synergy",                              "medium"),
    ("cutting-edge",                         "medium"),
    ("all-in-one",                           "high"),
    ("unlock your potential",                "high"),
    ("dream big",                            "high"),
    ("best-in-class",                        "medium"),
    ("world-class",                          "medium"),
]

_HIGH_SEVERITIES = {"high", "critical"}


# ── QuickComplianceCheck ──────────────────────────────────────────────────────

class QuickComplianceCheck:
    """
    Lightweight, synchronous compliance check — sensitive word scanning only.

    No LLM call. Designed for real-time UI feedback (违禁词 checker tool) that
    runs on every debounced keystroke.

    Words are loaded from the sensitive_words DB table on first use and
    cached in memory for 5 minutes. If the DB is unreachable, falls back
    to the built-in BRAND_FORBIDDEN list.

    Usage::

        checker = QuickComplianceCheck()
        result  = checker.check("这是最好的产品", language="zh-CN")
        # -> {"passed": False, "flags": [{...}], "suggestions": [...]}
    """

    _CACHE_TTL = 300  # seconds

    # Built-in seed words used when the DB table is empty or unreachable
    _BUILTIN_WORDS: list[dict] = [
        # ── Chinese absolute claims (high) ──────────────────────────────────
        {"word": "最",     "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "第一",   "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "唯一",   "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "顶级",   "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "最佳",   "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "最好",   "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "最便宜", "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "最高级", "severity": "high", "category": "absolute_claim",   "language": "zh-CN"},
        {"word": "国家级", "severity": "high", "category": "regulatory",       "language": "zh-CN"},
        # ── Chinese medical claims (critical) ──────────────────────────────
        {"word": "治愈",       "severity": "critical", "category": "medical_claim",  "language": "zh-CN"},
        {"word": "根治",       "severity": "critical", "category": "medical_claim",  "language": "zh-CN"},
        {"word": "特效",       "severity": "critical", "category": "medical_claim",  "language": "zh-CN"},
        {"word": "立即见效",   "severity": "critical", "category": "medical_claim",  "language": "zh-CN"},
        # ── Chinese regulatory triggers (critical) ─────────────────────────
        {"word": "投资保证", "severity": "critical", "category": "regulatory",    "language": "zh-CN"},
        {"word": "稳赚",     "severity": "critical", "category": "regulatory",    "language": "zh-CN"},
        {"word": "零风险",   "severity": "critical", "category": "regulatory",    "language": "zh-CN"},
        # ── English absolute claims (medium) ───────────────────────────────
        {"word": "guaranteed results", "severity": "medium", "category": "absolute_claim", "language": "en"},
        {"word": "100% success",       "severity": "medium", "category": "absolute_claim", "language": "en"},
        # ── English medical (high) ─────────────────────────────────────────
        {"word": "cure",     "severity": "high", "category": "medical_claim", "language": "en"},
        {"word": "treat",    "severity": "high", "category": "medical_claim", "language": "en"},
        {"word": "diagnose", "severity": "high", "category": "medical_claim", "language": "en"},
        # ── English brand-forbidden phrases (high) ─────────────────────────
        {"word": "game-changing",   "severity": "high",   "category": "brand_forbidden", "language": "en"},
        {"word": "revolutionary",   "severity": "medium", "category": "brand_forbidden", "language": "en"},
        {"word": "co-working space","severity": "high",   "category": "brand_forbidden", "language": "en"},
        {"word": "all-in-one",      "severity": "high",   "category": "brand_forbidden", "language": "en"},
        {"word": "world-class",     "severity": "medium", "category": "brand_forbidden", "language": "en"},
    ]

    _SUGGESTIONS: dict[str, str] = {
        "absolute_claim":   "Remove absolute superlatives — XHS/WeChat platforms flag these automatically",
        "medical_claim":    "Remove medical efficacy claims — requires licensed qualification (资质)",
        "regulatory":       "Remove financial guarantee language — violates platform and regulatory rules",
        "brand_forbidden":  "Replace with approved Hexa HUB phrases (see Brand Brain §9)",
    }

    def __init__(self) -> None:
        self._cached:  list[dict] = []
        self._expiry:  float      = 0.0

    def check(self, text: str, language: str = "zh-CN") -> dict:
        """
        Scan text for sensitive words.

        Returns
        -------
        {
            "passed":      bool,
            "flags":       [{"word", "severity", "category", "position", "length"}, ...],
            "suggestions": [str, ...]
        }
        """
        words   = self._get_words()
        flags:  list[dict] = []
        seen_suggestions: set[str] = set()
        suggestions: list[str] = []

        for word_info in words:
            if word_info.get("language", "zh-CN") != language:
                continue

            word    = word_info["word"]
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            for match in pattern.finditer(text):
                flags.append({
                    "word":     word,
                    "severity": word_info["severity"],
                    "category": word_info.get("category", "general"),
                    "position": match.start(),
                    "length":   len(word),
                })
                category = word_info.get("category", "general")
                tip = self._SUGGESTIONS.get(category, f"Remove or replace '{word}'")
                if tip not in seen_suggestions:
                    seen_suggestions.add(tip)
                    suggestions.append(tip)

        passed = not any(f["severity"] in _HIGH_SEVERITIES for f in flags)
        return {
            "passed":      passed,
            "flags":       sorted(flags, key=lambda f: f["position"]),
            "suggestions": suggestions,
        }

    # ── private ───────────────────────────────────────────────────────────────

    def _get_words(self) -> list[dict]:
        if time.monotonic() < self._expiry and self._cached:
            return self._cached

        try:
            loaded = self._load_from_db()
            if loaded:
                self._cached = loaded
                self._expiry = time.monotonic() + self._CACHE_TTL
                return self._cached
        except Exception:
            pass  # DB not available — use built-in list

        return self._BUILTIN_WORDS

    def _load_from_db(self) -> list[dict]:
        import psycopg2
        from backend.config import settings

        sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = psycopg2.connect(sync_url, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT word, severity, category, language FROM sensitive_words"
                )
                return [
                    {
                        "word":     r[0],
                        "severity": r[1],
                        "category": r[2] or "general",
                        "language": r[3],
                    }
                    for r in cur.fetchall()
                ]
        finally:
            conn.close()

    def invalidate_cache(self) -> None:
        """Force a DB reload on the next check() call."""
        self._expiry = 0.0


# Module-level singleton — import this in the API layer
quick_compliance = QuickComplianceCheck()


# ── ComplianceAgent ───────────────────────────────────────────────────────────

class ComplianceAgent(BaseAgent[ComplianceInput, ComplianceOutput]):
    agent_name       = "compliance_agent"
    default_provider = LLMProvider.ANTHROPIC
    required_skills  = ["copy-editing"]

    async def run(
        self,
        input_data: ComplianceInput,
        db:         Optional[AsyncSession] = None,
    ) -> ComplianceOutput:
        issues: list[ComplianceIssue] = []

        word_list  = await self._load_sensitive_words(db)
        copy_lower = input_data.copy.lower()

        for word, severity in word_list:
            if word.lower() in copy_lower:
                issues.append(ComplianceIssue(
                    severity    = "error" if severity in _HIGH_SEVERITIES else "warning",
                    category    = "sensitive_word",
                    description = f"Contains forbidden phrase: '{word}'",
                    suggestion  = f"Remove or replace '{word}' with an approved alternative",
                ))

        issues.extend(await self._llm_check(input_data))

        passed = not any(i.severity == "error" for i in issues)
        return ComplianceOutput(
            post_id    = input_data.post_id,
            passed     = passed,
            issues     = issues,
            checked_at = datetime.now(timezone.utc),
        )

    async def _load_sensitive_words(
        self, db: Optional[AsyncSession]
    ) -> list[tuple[str, str]]:
        if db is not None:
            from sqlalchemy import select
            from backend.db.models import SensitiveWord
            result = await db.execute(select(SensitiveWord))
            rows   = result.scalars().all()
            return [(r.word, r.severity.value) for r in rows]
        return _BRAND_FORBIDDEN

    async def _llm_check(self, input_data: ComplianceInput) -> list[ComplianceIssue]:
        system_prompt = self._build_system_prompt(load_prompt("compliance"))
        user_prompt   = (
            f"Platform: {input_data.platform.value}\n\n"
            f"Copy to review:\n{input_data.copy}\n\n"
            "Return the compliance JSON now."
        )
        response = await self.llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.2,
        )
        try:
            raw    = extract_json(response.content)
            issues = raw.get("issues", [])
            return [ComplianceIssue(**i) for i in issues]
        except Exception:
            return [ComplianceIssue(
                severity    = "warning",
                category    = "brand_guideline",
                description = "Automated compliance check returned unparseable output — manual review recommended",
                suggestion  = "Review copy manually before approval",
            )]
