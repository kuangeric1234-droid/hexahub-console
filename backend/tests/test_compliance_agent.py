"""
Unit tests for ComplianceAgent.

Tests cover:
- Sensitive word detection (no DB required — uses built-in brand forbidden list)
- LLM-based brand / platform checks
- passed=True / False logic
- DB path (mocked SQLAlchemy session)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.agents.compliance import ComplianceAgent, _BRAND_FORBIDDEN
from backend.agents.schemas.compliance import ComplianceInput, ComplianceIssue, ComplianceOutput
from backend.db.models import Platform
from tests.conftest import make_mock_llm


def _make_input(copy: str, platform: Platform = Platform.linkedin) -> ComplianceInput:
    return ComplianceInput(post_id=uuid4(), platform=platform, copy=copy)


CLEAN_COPY = (
    "Build locally, scale sustainably. "
    "Hexa Hub provides connected infrastructure for brands operating in Australia. "
    "One base. End-to-end operations. No fragmented vendors."
)

FORBIDDEN_COPY = "This game-changing co-working space is the best-in-class solution for all-in-one synergy."


# ── sensitive word detection ──────────────────────────────────────────────────

async def test_detects_forbidden_word_no_db():
    """Sensitive word scan works without a DB session (uses built-in list)."""
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input(FORBIDDEN_COPY))

    sensitive_issues = [i for i in output.issues if i.category == "sensitive_word"]
    assert len(sensitive_issues) >= 2  # "game-changing", "co-working space", etc.


async def test_forbidden_high_severity_is_error():
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input("This is a co-working space."))

    error_issues = [i for i in output.issues if i.severity == "error"]
    assert len(error_issues) >= 1


async def test_forbidden_medium_severity_is_warning():
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input("This is a game-changing platform."))

    warning_issues = [i for i in output.issues if i.severity == "warning" and i.category == "sensitive_word"]
    assert len(warning_issues) >= 1


async def test_clean_copy_no_sensitive_words():
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input(CLEAN_COPY))

    sensitive_issues = [i for i in output.issues if i.category == "sensitive_word"]
    assert len(sensitive_issues) == 0


# ── passed / failed logic ─────────────────────────────────────────────────────

async def test_passed_true_when_no_errors():
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input(CLEAN_COPY))

    assert output.passed is True


async def test_passed_false_when_error_present():
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input("Visit our co-working space today."))

    assert output.passed is False


async def test_passed_false_when_llm_returns_error():
    llm_errors = {
        "issues": [
            {
                "severity":    "error",
                "category":    "platform_policy",
                "description": "Contains false claim about services",
                "suggestion":  "Remove unverified claim",
            }
        ]
    }
    mock_llm = make_mock_llm(llm_errors)
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input(CLEAN_COPY))

    assert output.passed is False
    assert any(i.category == "platform_policy" for i in output.issues)


async def test_warnings_only_does_not_fail():
    """Only warnings (no errors) → passed=True."""
    llm_warnings = {
        "issues": [
            {
                "severity":    "warning",
                "category":    "brand_guideline",
                "description": "Passive voice detected",
                "suggestion":  "Rewrite in active voice",
            }
        ]
    }
    mock_llm = make_mock_llm(llm_warnings)
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input(CLEAN_COPY))

    assert output.passed is True
    assert len(output.issues) >= 1


# ── output schema ─────────────────────────────────────────────────────────────

async def test_output_has_checked_at_timestamp():
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input(CLEAN_COPY))

    assert isinstance(output.checked_at, datetime)
    assert output.checked_at.tzinfo is not None  # timezone-aware


async def test_post_id_matches_input():
    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    inp      = _make_input(CLEAN_COPY)
    output   = await agent(inp)
    assert output.post_id == inp.post_id


# ── LLM parse error fallback ──────────────────────────────────────────────────

async def test_unparseable_llm_response_becomes_warning():
    """If LLM returns non-JSON, agent adds a 'manual review' warning instead of crashing."""
    from unittest.mock import AsyncMock
    from backend.llm.client import LLMProvider, LLMResponse

    bad_llm = AsyncMock()
    bad_llm.complete = AsyncMock(return_value=LLMResponse(
        content="Sorry, I cannot evaluate this content.",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=10,
        output_tokens=10,
    ))

    agent  = ComplianceAgent(llm_client=bad_llm)
    output = await agent(_make_input(CLEAN_COPY))
    assert any("manual review" in i.description.lower() for i in output.issues)


# ── DB path ───────────────────────────────────────────────────────────────────

async def test_uses_db_words_when_session_provided():
    """When a DB session is given, use DB words instead of built-in list."""
    mock_word      = MagicMock()
    mock_word.word = "synergy"
    mock_word.severity.value = "medium"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_word]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_llm = make_mock_llm({"issues": []})
    agent    = ComplianceAgent(llm_client=mock_llm)
    output   = await agent(_make_input("We offer synergy between teams."), db=mock_db)

    sensitive = [i for i in output.issues if i.category == "sensitive_word"]
    assert len(sensitive) >= 1
    assert mock_db.execute.await_count >= 1
