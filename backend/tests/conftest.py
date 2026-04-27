"""
Shared pytest fixtures.

LLM calls are mocked at the LLMClient.complete() boundary so tests never
hit real APIs or need credentials.
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.agents.schemas.strategy import StrategyInput, StrategyOutput
from backend.db.models import Platform
from backend.llm.client import LLMProvider, LLMResponse


# ── reusable mock LLM factory ─────────────────────────────────────────────────

def make_mock_llm(response_json: dict) -> AsyncMock:
    """Return a mock LLMClient whose complete() resolves to response_json."""
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps(response_json),
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            input_tokens=500,
            output_tokens=400,
        )
    )
    return client


# ── common input fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def campaign_id():
    return uuid4()


@pytest.fixture
def strategy_input(campaign_id):
    return StrategyInput(
        campaign_id=campaign_id,
        name="Q2 2026 Awareness Campaign",
        brief=(
            "Build awareness for Hexa Hub among cross-border e-commerce brands "
            "entering Australia. Focus on operational credibility and speed-to-launch."
        ),
        objective="Generate 50 qualified space enquiries within 90 days",
        kpis={"enquiries": 50, "engagement_rate": 3.5, "follower_growth": 500},
        start_date=date(2026, 4, 1),
        end_date=date(2026, 6, 30),
        platforms=[Platform.linkedin, Platform.instagram],
    )


MOCK_STRATEGY_RESPONSE = {
    "pillars": [
        {"name": "Operations",  "description": "Day-to-day ops and infrastructure content", "weight": 0.30},
        {"name": "Ecosystem",   "description": "Partner and integration showcase",           "weight": 0.25},
        {"name": "What",        "description": "Brand awareness and positioning",            "weight": 0.25},
        {"name": "Community",   "description": "Events, founders, team",                     "weight": 0.20},
    ],
    "cadence": [
        {
            "platform": "linkedin",
            "posts_per_week": 3,
            "best_days": ["Monday", "Wednesday", "Friday"],
            "best_time_utc": "09:00",
            "tone_notes": "Professional, insight-led. Hook → insight → CTA.",
        },
        {
            "platform": "instagram",
            "posts_per_week": 4,
            "best_days": ["Tuesday", "Thursday", "Saturday", "Sunday"],
            "best_time_utc": "18:00",
            "tone_notes": "Visual, punchy. Real photography, hexagon motif.",
        },
    ],
    "kpi_targets": [
        {"metric": "engagement_rate",  "target": 3.5,  "unit": "percent"},
        {"metric": "space_enquiries",  "target": 50,   "unit": "count"},
        {"metric": "follower_growth",  "target": 500,  "unit": "count"},
    ],
    "rationale": (
        "LinkedIn captures decision-makers at the point of AU expansion. "
        "Instagram builds social proof for the operational brand. "
        "Operations pillar dominates to lead with credibility."
    ),
}


@pytest.fixture
def mock_strategy_llm():
    return make_mock_llm(MOCK_STRATEGY_RESPONSE)


@pytest.fixture
def strategy_output(campaign_id) -> StrategyOutput:
    """Pre-built StrategyOutput for use as CalendarAgent input."""
    from backend.agents.schemas.strategy import KPITarget, PillarDef, PlatformCadence
    return StrategyOutput(
        campaign_id=campaign_id,
        pillars=[
            PillarDef(name="Operations", description="Ops content", weight=0.35),
            PillarDef(name="Ecosystem",  description="Partners",    weight=0.35),
            PillarDef(name="Community",  description="Events",      weight=0.30),
        ],
        cadence=[
            PlatformCadence(
                platform=Platform.linkedin,
                posts_per_week=3,
                best_days=["Monday", "Wednesday", "Friday"],
                best_time_utc="09:00",
                tone_notes="Professional",
            ),
        ],
        kpi_targets=[
            KPITarget(metric="engagement_rate", target=3.5, unit="percent"),
        ],
        rationale="Test strategy.",
    )
