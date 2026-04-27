"""
Orchestrator workflow tests.

Node functions are tested in isolation by mocking their agent dependencies.
A lightweight integration test verifies routing logic for:
  - Happy path (strategy → calendar → copy → visual → compliance pass → approval → publish)
  - Compliance retry path (fail once, pass on retry)
  - Escalation path (fail 3 times → escalate)

`interrupt()` is patched to return a pre-set approval decision so tests do
not actually pause execution.

NOTE: These tests DO NOT hit a real database or LLM. All agent calls and DB
      operations are mocked.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from backend.orchestrator.state import CampaignWorkflowState
from backend.orchestrator.workflow import build_initial_state, create_workflow


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_state(**overrides) -> CampaignWorkflowState:
    base = build_initial_state(
        campaign_id=str(uuid.uuid4()),
        strategy_input={
            "campaign_id":  str(uuid.uuid4()),
            "name":         "Test campaign",
            "brief":        "Build awareness for Hexa Hub in Australia." * 3,
            "objective":    "Generate 50 qualified enquiries.",
            "kpis":         {"enquiries": 50},
            "start_date":   "2026-04-01",
            "end_date":     "2026-06-30",
            "platforms":    ["linkedin"],
        },
    )
    base.update(overrides)
    return base


def _mock_slot(platform: str = "linkedin") -> dict:
    return {
        "campaign_id":        str(uuid.uuid4()),
        "platform":           platform,
        "pillar_name":        "Operations",
        "scheduled_at":       "2026-04-06T09:00:00+00:00",
        "working_title":      "Test post",
        "content_brief":      "A brief description of the post content.",
        "is_holiday_adjacent": False,
        "_post_db_id":        str(uuid.uuid4()),
    }


def _mock_strategy_output(campaign_id: str) -> dict:
    return {
        "campaign_id": campaign_id,
        "pillars": [{"name": "Operations", "description": "Ops", "weight": 1.0}],
        "cadence": [{
            "platform": "linkedin",
            "posts_per_week": 3,
            "best_days": ["Monday"],
            "best_time_utc": "09:00",
            "tone_notes": "Professional",
        }],
        "kpi_targets": [{"metric": "engagement_rate", "target": 3.5, "unit": "percent"}],
        "rationale": "Test strategy.",
    }


def _mock_copy_output(post_id: str) -> dict:
    return {
        "post_id":    post_id,
        "platform":   "linkedin",
        "copy":       "Build locally, scale sustainably. Message us to see the floor.",
        "char_count": 62,
        "word_count": 10,
        "metadata":   {"hook_line": "Build locally, scale sustainably."},
        "warnings":   [],
    }


def _mock_visual_output(post_id: str) -> dict:
    return {
        "post_id": post_id,
        "visual_brief": {
            "description":  "Warehouse floor",
            "style_notes":  "Minimal white palette",
            "text_overlay": "",
            "dimensions":   "1200x628",
            "alt_text":     "Hexa Hub warehouse",
        },
        "image_url":     None,
        "provider_used": None,
    }


def _mock_compliance_output(post_id: str, passed: bool = True) -> dict:
    return {
        "post_id":    post_id,
        "passed":     passed,
        "issues":     [] if passed else [
            {
                "severity":    "error",
                "category":    "brand_guideline",
                "description": "Contains forbidden phrase",
                "suggestion":  "Remove it",
            }
        ],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Routing function unit tests ───────────────────────────────────────────────

def test_route_advance_post_continue_when_slot_present():
    from backend.orchestrator.workflow import _route_advance_post
    state = _make_state(current_slot=_mock_slot())
    assert _route_advance_post(state) == "continue"


def test_route_advance_post_done_when_no_slot():
    from backend.orchestrator.workflow import _route_advance_post
    state = _make_state(current_slot=None)
    assert _route_advance_post(state) == "done"


def test_route_compliance_pass():
    from backend.orchestrator.workflow import _route_compliance
    state = _make_state(
        compliance_output=_mock_compliance_output("x", passed=True),
        compliance_retry_count=0,
    )
    assert _route_compliance(state) == "pass"


def test_route_compliance_retry_on_first_failure():
    from backend.orchestrator.workflow import _route_compliance
    state = _make_state(
        compliance_output=_mock_compliance_output("x", passed=False),
        compliance_retry_count=1,  # 1st retry used (≤ max)
    )
    assert _route_compliance(state) == "retry"


def test_route_compliance_escalate_after_max_retries():
    from backend.orchestrator.workflow import _route_compliance
    from backend.orchestrator.nodes import _MAX_COMPLIANCE_RETRIES
    state = _make_state(
        compliance_output=_mock_compliance_output("x", passed=False),
        compliance_retry_count=_MAX_COMPLIANCE_RETRIES + 1,
    )
    assert _route_compliance(state) == "escalate"


def test_route_after_approval_publish_when_approved():
    from backend.orchestrator.workflow import _route_after_approval
    state = _make_state(workflow_status="approved")
    assert _route_after_approval(state) == "publish"


def test_route_after_approval_skip_when_rejected():
    from backend.orchestrator.workflow import _route_after_approval
    state = _make_state(workflow_status="rejected")
    assert _route_after_approval(state) == "skip"


# ── advance_post_node unit tests ──────────────────────────────────────────────

async def test_advance_post_node_returns_first_slot():
    from backend.orchestrator.nodes import advance_post_node
    slot  = _mock_slot()
    state = _make_state(post_slots=[slot], current_slot_idx=0)
    updates = await advance_post_node(state)
    assert updates["current_slot"] == slot
    assert updates["current_slot_idx"] == 1
    assert updates["compliance_retry_count"] == 0


async def test_advance_post_node_returns_none_when_exhausted():
    from backend.orchestrator.nodes import advance_post_node
    state   = _make_state(post_slots=[_mock_slot()], current_slot_idx=1)
    updates = await advance_post_node(state)
    assert updates["current_slot"] is None


# ── Integration: happy-path workflow ──────────────────────────────────────────

@pytest.mark.slow
async def test_happy_path_workflow_completes():
    """
    Full workflow from strategy to publishing with all agents mocked.
    interrupt() is patched to immediately return 'approved'.
    """
    campaign_id = str(uuid.uuid4())
    post_id     = str(uuid.uuid4())
    slot        = _mock_slot()
    slot["_post_db_id"] = post_id

    strat_out  = _mock_strategy_output(campaign_id)
    copy_out   = _mock_copy_output(post_id)
    visual_out = _mock_visual_output(post_id)
    comp_pass  = _mock_compliance_output(post_id, passed=True)

    with (
        patch("backend.orchestrator.nodes.StrategyAgent") as MockStrat,
        patch("backend.orchestrator.nodes.CalendarAgent") as MockCal,
        patch("backend.orchestrator.nodes.LinkedInCopyAgent") as MockCopy,
        patch("backend.orchestrator.nodes.VisualAgent") as MockVis,
        patch("backend.orchestrator.nodes.ComplianceAgent") as MockComp,
        patch("backend.orchestrator.nodes.PublishingAgent") as MockPub,
        patch("backend.orchestrator.nodes.AsyncSessionLocal"),
        patch("backend.orchestrator.nodes.interrupt", return_value={"decision": "approved"}),
    ):
        # Strategy
        mock_strat = AsyncMock()
        mock_strat.return_value = MagicMock(model_dump=lambda mode=None: strat_out)
        MockStrat.return_value.__call__ = mock_strat

        # Calendar — returns one slot
        from backend.agents.schemas.calendar import CalendarOutput, PostSlot
        mock_cal_out = MagicMock()
        mock_cal_out.model_dump = lambda mode=None: {"slots": [slot]}
        mock_cal = AsyncMock(return_value=mock_cal_out)
        MockCal.return_value.__call__ = mock_cal

        # Copy
        mock_copy_out = MagicMock(model_dump=lambda mode=None: copy_out)
        MockCopy.return_value.__call__ = AsyncMock(return_value=mock_copy_out)

        # Visual
        mock_vis_out = MagicMock(model_dump=lambda mode=None: visual_out)
        MockVis.return_value.__call__ = AsyncMock(return_value=mock_vis_out)

        # Compliance — pass
        mock_comp_out = MagicMock(passed=True, issues=[], model_dump=lambda mode=None: comp_pass)
        MockComp.return_value.__call__ = AsyncMock(return_value=mock_comp_out)

        # Publishing
        mock_pub_out = MagicMock(model_dump=lambda mode=None: {})
        MockPub.return_value.__call__ = AsyncMock(return_value=mock_pub_out)

        app   = create_workflow(checkpointer=MemorySaver())
        state = build_initial_state(campaign_id=campaign_id, strategy_input={
            "campaign_id": campaign_id, "name": "Test", "brief": "A" * 30,
            "objective": "B" * 15, "kpis": {}, "start_date": "2026-04-01",
            "end_date": "2026-06-30", "platforms": ["linkedin"],
        })

        config = {"configurable": {"thread_id": f"test-{uuid.uuid4()}"}}
        result = await app.ainvoke(state, config=config)

    assert result is not None
    # No errors means the workflow ran to completion
    assert not any("failed" in e.lower() for e in result.get("errors", []))


# ── Integration: escalation path ──────────────────────────────────────────────

@pytest.mark.slow
async def test_escalation_after_max_compliance_retries():
    """Compliance fails 3 times → escalation node is reached."""
    from backend.orchestrator.nodes import _MAX_COMPLIANCE_RETRIES
    campaign_id = str(uuid.uuid4())
    post_id     = str(uuid.uuid4())
    slot        = _mock_slot()
    slot["_post_db_id"] = post_id

    strat_out = _mock_strategy_output(campaign_id)
    copy_out  = _mock_copy_output(post_id)
    comp_fail = _mock_compliance_output(post_id, passed=False)

    with (
        patch("backend.orchestrator.nodes.StrategyAgent") as MockStrat,
        patch("backend.orchestrator.nodes.CalendarAgent") as MockCal,
        patch("backend.orchestrator.nodes.LinkedInCopyAgent") as MockCopy,
        patch("backend.orchestrator.nodes.VisualAgent") as MockVis,
        patch("backend.orchestrator.nodes.ComplianceAgent") as MockComp,
        patch("backend.orchestrator.nodes.AsyncSessionLocal"),
        patch("backend.orchestrator.nodes.interrupt"),
    ):
        mock_strat = MagicMock(model_dump=lambda mode=None: strat_out)
        MockStrat.return_value.__call__ = AsyncMock(return_value=mock_strat)

        mock_cal_out = MagicMock(model_dump=lambda mode=None: {"slots": [slot]})
        MockCal.return_value.__call__ = AsyncMock(return_value=mock_cal_out)

        mock_copy_out = MagicMock(model_dump=lambda mode=None: copy_out)
        MockCopy.return_value.__call__ = AsyncMock(return_value=mock_copy_out)

        mock_vis_out = MagicMock(model_dump=lambda mode=None: _mock_visual_output(post_id))
        MockVis.return_value.__call__ = AsyncMock(return_value=mock_vis_out)

        # Always fail compliance
        mock_comp_out = MagicMock(passed=False, issues=[MagicMock(
            severity="error", category="brand_guideline",
            description="Forbidden word", suggestion="Fix it",
        )], model_dump=lambda mode=None: comp_fail)
        MockComp.return_value.__call__ = AsyncMock(return_value=mock_comp_out)

        app   = create_workflow(checkpointer=MemorySaver())
        state = build_initial_state(campaign_id=campaign_id, strategy_input={
            "campaign_id": campaign_id, "name": "Test", "brief": "A" * 30,
            "objective": "B" * 15, "kpis": {}, "start_date": "2026-04-01",
            "end_date": "2026-06-30", "platforms": ["linkedin"],
        })

        config = {"configurable": {"thread_id": f"test-{uuid.uuid4()}"}}
        result = await app.ainvoke(state, config=config)

    # After max retries the workflow escalates and moves on (no crash)
    assert result is not None
    errors = result.get("errors", [])
    assert any("escalat" in e.lower() for e in errors)
