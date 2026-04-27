"""
LangGraph workflow state.

All values must be JSON-serialisable so they can be persisted in the
checkpointer (Postgres in production, MemorySaver in dev/test).
UUIDs are stored as strings; datetimes as ISO 8601 strings.
"""
from __future__ import annotations

import operator
from typing import Annotated, Optional

from typing_extensions import TypedDict


class CampaignWorkflowState(TypedDict):
    # ── Campaign identity ─────────────────────────────────────────────────────
    campaign_id:    str    # UUID as string
    strategy_input: dict   # serialised StrategyInput (model_dump mode='json')

    # ── Phase outputs ─────────────────────────────────────────────────────────
    strategy_output: Optional[dict]   # serialised StrategyOutput
    post_slots:      list[dict]       # all PostSlots from CalendarAgent

    # ── Per-post loop ─────────────────────────────────────────────────────────
    current_slot_idx: int             # points to the NEXT slot to process
    current_slot:     Optional[dict]  # the slot currently being worked on

    # Post DB record created for the current slot
    post_db_id: Optional[str]         # UUID string

    # ── Current post agent outputs ────────────────────────────────────────────
    copy_output:            Optional[dict]
    visual_output:          Optional[dict]
    compliance_output:      Optional[dict]
    compliance_feedback:    Optional[str]  # summary of issues passed back to copy agent
    compliance_retry_count: int

    # ── Approval ──────────────────────────────────────────────────────────────
    # "running" | "waiting_approval" | "approved" | "rejected"
    # | "completed" | "escalated" | "failed"
    workflow_status:  str

    # ── Bookkeeping ───────────────────────────────────────────────────────────
    completed_post_ids: list[str]
    # errors uses Annotated[list, operator.add] so each node can append
    # without overwriting the whole list
    errors: Annotated[list[str], operator.add]
