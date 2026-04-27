"""
LangGraph campaign workflow.

Graph topology
--------------

    strategy → calendar → advance_post ←────────────────────────────────────┐
                              │                                              │
                    (more slots)│(no slots)                                  │
                              ↓        ↓                                     │
                             copy     END                                    │
                              ↓                                              │
                            visual                                           │
                              ↓                                              │
                          compliance                                         │
                         /    |     \\                                       │
                       pass  retry  escalate                                 │
                       /       |        \\                                   │
              approval_queue  copy    escalation ─────────────────────────────┘
                 /      \\                 ↑
             approved  rejected ──────────┘
               /
          publishing ──────────────────────────────────────────────────────────┘

Key behaviours
--------------
- Compliance fails → retry with feedback (max 2 retries)
- 3rd compliance fail → escalation (post marked failed, loop to next post)
- Approval rejected → skip publishing, loop to next post
- Approval approved → publish, loop to next post
- All posts processed → END
"""
from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from backend.orchestrator.nodes import (
    advance_post_node,
    approval_queue_node,
    calendar_node,
    compliance_node,
    copy_node,
    escalation_node,
    publishing_node,
    strategy_node,
    visual_node,
    _MAX_COMPLIANCE_RETRIES,
)
from backend.orchestrator.state import CampaignWorkflowState

# ── Routing functions ─────────────────────────────────────────────────────────

def _route_after_calendar(state: CampaignWorkflowState) -> str:
    if state.get("workflow_status") == "failed":
        return END
    return "has_posts" if state.get("post_slots") else END


def _route_advance_post(state: CampaignWorkflowState) -> str:
    if state.get("workflow_status") == "failed":
        return END
    return "continue" if state.get("current_slot") else "done"


def _route_compliance(state: CampaignWorkflowState) -> str:
    if state.get("workflow_status") == "failed":
        return END
    output = state.get("compliance_output", {})
    if output.get("passed", False):
        return "pass"
    retry_count = state.get("compliance_retry_count", 0)
    return "retry" if retry_count <= _MAX_COMPLIANCE_RETRIES else "escalate"


def _route_after_approval(state: CampaignWorkflowState) -> str:
    return "publish" if state.get("workflow_status") == "approved" else "skip"


# ── Graph factory ─────────────────────────────────────────────────────────────

def create_workflow(checkpointer=None):
    """
    Build and compile the campaign workflow graph.

    Parameters
    ----------
    checkpointer
        LangGraph checkpointer instance.  Defaults to MemorySaver (in-memory,
        suitable for dev/test).  Pass AsyncPostgresSaver for production.

    Returns
    -------
    CompiledStateGraph
        A compiled, ready-to-invoke LangGraph application.
    """
    g = StateGraph(CampaignWorkflowState)

    # ── Nodes ──────────────────────────────────────────────────────────────
    g.add_node("strategy",       strategy_node)
    g.add_node("calendar",       calendar_node)
    g.add_node("advance_post",   advance_post_node)
    g.add_node("copy",           copy_node)
    g.add_node("visual",         visual_node)
    g.add_node("compliance",     compliance_node)
    g.add_node("approval_queue", approval_queue_node)
    g.add_node("publishing",     publishing_node)
    g.add_node("escalation",     escalation_node)

    # ── Entry & fixed edges ────────────────────────────────────────────────
    g.set_entry_point("strategy")
    g.add_edge("strategy", "calendar")
    g.add_edge("copy",     "visual")
    g.add_edge("visual",   "compliance")

    # ── Conditional: after calendar, check for posts ───────────────────────
    g.add_conditional_edges(
        "calendar",
        _route_after_calendar,
        {"has_posts": "advance_post", END: END},
    )

    # ── Conditional: advance_post → (next post | done) ─────────────────────
    g.add_conditional_edges(
        "advance_post",
        _route_advance_post,
        {"continue": "copy", "done": END},
    )

    # ── Conditional: compliance result ────────────────────────────────────
    g.add_conditional_edges(
        "compliance",
        _route_compliance,
        {"pass": "approval_queue", "retry": "copy", "escalate": "escalation"},
    )

    # ── Conditional: approval decision ────────────────────────────────────
    g.add_conditional_edges(
        "approval_queue",
        _route_after_approval,
        {"publish": "publishing", "skip": "advance_post"},
    )

    # ── Back to loop ──────────────────────────────────────────────────────
    g.add_edge("publishing", "advance_post")
    g.add_edge("escalation", "advance_post")

    return g.compile(checkpointer=checkpointer or MemorySaver())


def build_initial_state(
    campaign_id: str,
    strategy_input: dict,
) -> CampaignWorkflowState:
    """Convenience constructor for the initial workflow state."""
    return CampaignWorkflowState(
        campaign_id=campaign_id,
        strategy_input=strategy_input,
        strategy_output=None,
        post_slots=[],
        current_slot_idx=0,
        current_slot=None,
        post_db_id=None,
        copy_output=None,
        visual_output=None,
        compliance_output=None,
        compliance_feedback=None,
        compliance_retry_count=0,
        workflow_status="running",
        completed_post_ids=[],
        errors=[],
    )
