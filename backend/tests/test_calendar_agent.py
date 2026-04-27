"""
Unit tests for CalendarAgent.

LLM calls are mocked. Tests verify parsing, timezone handling,
holiday flagging, and schema validation.
"""
from __future__ import annotations

from datetime import date, timezone
from uuid import uuid4

import pytest

from backend.agents.calendar import CalendarAgent
from backend.agents.schemas.calendar import CalendarInput, CalendarOutput
from backend.db.models import Platform
from tests.conftest import make_mock_llm


def _make_calendar_input(campaign_id, strategy_output, start=None, end=None):
    return CalendarInput(
        campaign_id=campaign_id,
        strategy=strategy_output,
        start_date=start or date(2026, 4, 1),
        end_date=end   or date(2026, 4, 30),
    )


def _mock_calendar_response(campaign_id, slots: list[dict]) -> dict:
    platform_counts: dict[str, int] = {}
    for s in slots:
        platform_counts[s["platform"]] = platform_counts.get(s["platform"], 0) + 1
    return {
        "slots": slots,
        "total_posts": len(slots),
        "platform_breakdown": platform_counts,
        "holiday_notes": [],
    }


SAMPLE_SLOTS = [
    {
        "campaign_id": "00000000-0000-0000-0000-000000000000",  # overwritten by agent
        "platform": "linkedin",
        "pillar_name": "Operations",
        "scheduled_at": "2026-04-06T09:00:00+00:00",
        "working_title": "Inside Hexa Hub's fulfilment floor",
        "content_brief": "Show how our logistics setup cuts time-to-dispatch for cross-border brands.",
        "is_holiday_adjacent": False,
    },
    {
        "campaign_id": "00000000-0000-0000-0000-000000000000",
        "platform": "linkedin",
        "pillar_name": "Ecosystem",
        "scheduled_at": "2026-04-08T09:00:00+00:00",
        "working_title": "Three integrations that changed how we scale",
        "content_brief": "Highlight IT and logistics partner integrations that reduce manual ops.",
        "is_holiday_adjacent": False,
    },
    {
        "campaign_id": "00000000-0000-0000-0000-000000000000",
        "platform": "linkedin",
        "pillar_name": "Community",
        "scheduled_at": "2026-04-10T09:00:00+00:00",
        "working_title": "A founder's first 30 days in AU",
        "content_brief": "Feature a cross-border brand's launch journey from arrival to first shipment.",
        "is_holiday_adjacent": False,
    },
]


# ── happy path ────────────────────────────────────────────────────────────────

async def test_calendar_agent_returns_calendar_output(campaign_id, strategy_output):
    mock_resp = _mock_calendar_response(campaign_id, SAMPLE_SLOTS)
    agent     = CalendarAgent(llm_client=make_mock_llm(mock_resp))
    inp       = _make_calendar_input(campaign_id, strategy_output)

    output = await agent(inp)

    assert isinstance(output, CalendarOutput)
    assert output.total_posts == len(SAMPLE_SLOTS)
    assert output.campaign_id == campaign_id


async def test_slots_have_timezone_aware_datetimes(campaign_id, strategy_output):
    mock_resp = _mock_calendar_response(campaign_id, SAMPLE_SLOTS)
    agent     = CalendarAgent(llm_client=make_mock_llm(mock_resp))
    output    = await agent(_make_calendar_input(campaign_id, strategy_output))

    for slot in output.slots:
        assert slot.scheduled_at.tzinfo is not None, (
            f"slot {slot.working_title!r} has naive datetime"
        )


async def test_platform_breakdown_matches_slots(campaign_id, strategy_output):
    mock_resp = _mock_calendar_response(campaign_id, SAMPLE_SLOTS)
    agent     = CalendarAgent(llm_client=make_mock_llm(mock_resp))
    output    = await agent(_make_calendar_input(campaign_id, strategy_output))

    for platform, count in output.platform_breakdown.items():
        actual = sum(1 for s in output.slots if s.platform.value == platform)
        assert actual == count


async def test_campaign_id_is_set_on_all_slots(campaign_id, strategy_output):
    """Agent overwrites any campaign_id from the LLM with the authoritative one."""
    mock_resp = _mock_calendar_response(campaign_id, SAMPLE_SLOTS)
    agent     = CalendarAgent(llm_client=make_mock_llm(mock_resp))
    output    = await agent(_make_calendar_input(campaign_id, strategy_output))

    for slot in output.slots:
        assert slot.campaign_id == campaign_id


# ── timezone handling ─────────────────────────────────────────────────────────

async def test_naive_datetime_gets_utc(campaign_id, strategy_output):
    """If LLM returns a naive datetime, agent assigns UTC."""
    slots_naive = [
        {**SAMPLE_SLOTS[0], "scheduled_at": "2026-04-06T09:00:00"}  # no tz
    ]
    mock_resp = _mock_calendar_response(campaign_id, slots_naive)
    agent     = CalendarAgent(llm_client=make_mock_llm(mock_resp))
    output    = await agent(_make_calendar_input(campaign_id, strategy_output))

    assert output.slots[0].scheduled_at.tzinfo == timezone.utc


# ── holiday adjacency ─────────────────────────────────────────────────────────

async def test_holiday_adjacent_flag_set_for_618(campaign_id, strategy_output):
    """A slot on 2026-06-15 falls inside the 618 festival window."""
    slot_618 = [
        {
            **SAMPLE_SLOTS[0],
            "platform": "linkedin",
            "scheduled_at": "2026-06-15T09:00:00+00:00",
            "is_holiday_adjacent": False,  # LLM said false; agent should override
        }
    ]
    mock_resp = _mock_calendar_response(campaign_id, slot_618)
    agent     = CalendarAgent(llm_client=make_mock_llm(mock_resp))
    output    = await agent(
        _make_calendar_input(campaign_id, strategy_output,
                             start=date(2026, 6, 1), end=date(2026, 6, 30))
    )

    assert output.slots[0].is_holiday_adjacent is True


# ── validation ────────────────────────────────────────────────────────────────

async def test_validate_rejects_empty_pillars(campaign_id, strategy_output):
    strategy_output.pillars = []
    agent = CalendarAgent()
    inp   = _make_calendar_input(campaign_id, strategy_output)
    with pytest.raises(ValueError, match="pillar"):
        agent.validate(inp)


async def test_validate_rejects_start_after_end(campaign_id, strategy_output):
    with pytest.raises(Exception):
        CalendarInput(
            campaign_id=campaign_id,
            strategy=strategy_output,
            start_date=date(2026, 12, 31),
            end_date=date(2026, 1, 1),
        )


# ── total_posts consistency ───────────────────────────────────────────────────

async def test_total_posts_equals_slot_count(campaign_id, strategy_output):
    mock_resp = _mock_calendar_response(campaign_id, SAMPLE_SLOTS)
    agent     = CalendarAgent(llm_client=make_mock_llm(mock_resp))
    output    = await agent(_make_calendar_input(campaign_id, strategy_output))

    assert output.total_posts == len(output.slots)
