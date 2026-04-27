"""
Unit tests for StrategyAgent.

LLM calls are mocked via the make_mock_llm fixture in conftest.py.
"""
from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

import pytest

from backend.agents.schemas.strategy import StrategyInput, StrategyOutput
from backend.agents.strategy import StrategyAgent
from backend.db.models import Platform
from tests.conftest import MOCK_STRATEGY_RESPONSE, make_mock_llm


# ── happy path ────────────────────────────────────────────────────────────────

async def test_strategy_agent_returns_strategy_output(strategy_input, mock_strategy_llm):
    agent  = StrategyAgent(llm_client=mock_strategy_llm)
    output = await agent(strategy_input)

    assert isinstance(output, StrategyOutput)
    assert output.campaign_id == strategy_input.campaign_id
    assert len(output.pillars) >= 1
    assert len(output.cadence) >= 1
    assert len(output.kpi_targets) >= 1


async def test_pillar_weights_sum_to_one(strategy_input, mock_strategy_llm):
    agent  = StrategyAgent(llm_client=mock_strategy_llm)
    output = await agent(strategy_input)

    total = sum(p.weight for p in output.pillars)
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected ~1.0"


async def test_cadence_only_includes_requested_platforms(strategy_input, mock_strategy_llm):
    agent  = StrategyAgent(llm_client=mock_strategy_llm)
    output = await agent(strategy_input)

    returned  = {c.platform for c in output.cadence}
    requested = set(strategy_input.platforms)
    assert returned.issubset(requested), f"Unexpected platforms: {returned - requested}"


async def test_llm_called_once(strategy_input, mock_strategy_llm):
    agent = StrategyAgent(llm_client=mock_strategy_llm)
    await agent(strategy_input)

    mock_strategy_llm.complete.assert_awaited_once()


# ── weight normalisation ──────────────────────────────────────────────────────

async def test_weights_are_normalised_when_not_summing_to_one(strategy_input):
    """Agent should normalise weights that don't sum to 1.0."""
    bad_weights = {
        **MOCK_STRATEGY_RESPONSE,
        "pillars": [
            {"name": "A", "description": "a", "weight": 0.5},
            {"name": "B", "description": "b", "weight": 0.5},
            {"name": "C", "description": "c", "weight": 0.5},  # total = 1.5
        ],
    }
    agent  = StrategyAgent(llm_client=make_mock_llm(bad_weights))
    output = await agent(strategy_input)

    total = sum(p.weight for p in output.pillars)
    assert abs(total - 1.0) < 0.01


# ── validation ────────────────────────────────────────────────────────────────

async def test_validate_rejects_start_after_end(mock_strategy_llm):
    with pytest.raises(Exception):  # Pydantic model_validator fires at construction
        StrategyInput(
            campaign_id=uuid4(),
            name="Bad",
            brief="This is a long enough brief to pass validation checks.",
            objective="Test objective that is long enough.",
            kpis={},
            start_date=date(2026, 12, 31),
            end_date=date(2026, 1, 1),
            platforms=[Platform.linkedin],
        )


def test_validate_rejects_empty_brief(strategy_input):
    agent = StrategyAgent()
    strategy_input.brief = "   "
    with pytest.raises(ValueError, match="brief"):
        agent.validate(strategy_input)


def test_validate_rejects_no_platforms(strategy_input):
    agent = StrategyAgent()
    strategy_input.platforms = []
    with pytest.raises((ValueError, Exception)):
        agent.validate(strategy_input)


# ── no db session — log falls back to structlog ───────────────────────────────

async def test_runs_without_db_session(strategy_input, mock_strategy_llm):
    agent  = StrategyAgent(llm_client=mock_strategy_llm)
    output = await agent(strategy_input, db=None)
    assert isinstance(output, StrategyOutput)
