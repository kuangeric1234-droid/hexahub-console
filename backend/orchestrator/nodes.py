"""
LangGraph node functions.

Each node:
- Accepts the full CampaignWorkflowState
- Returns a dict of state keys to update (partial update semantics)
- Creates its own DB session if needed (not shared across nodes)
- Never raises — failures are captured in state["errors"]

Approval gate
-------------
approval_queue_node calls langgraph.types.interrupt() which causes LangGraph
to save state and pause execution.  The workflow is resumed by calling:

    from langgraph.types import Command
    await app.ainvoke(
        Command(resume={"decision": "approved", "feedback": "LGTM"}),
        config={"configurable": {"thread_id": thread_id}},
    )

After resume, the interrupt() call returns the dict passed to Command(resume=...).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from langgraph.types import interrupt

from backend.agents.compliance import ComplianceAgent
from backend.agents.copy import (
    BlogCopyAgent,
    InstagramCopyAgent,
    LinkedInCopyAgent,
    WeChatMomentsAgent,
    XiaohongshuCopyAgent,
)
from backend.agents.copy.base import BaseCopyAgent
from backend.agents.publish import PublishingAgent
from backend.agents.schemas.calendar import CalendarInput
from backend.agents.schemas.compliance import ComplianceInput
from backend.agents.schemas.copy import CopyInput
from backend.agents.schemas.publish import PublishInput
from backend.agents.schemas.strategy import StrategyInput
from backend.agents.schemas.visual import VisualInput
from backend.agents.strategy import StrategyAgent
from backend.agents.calendar import CalendarAgent
from backend.agents.visual import VisualAgent
from backend.db.database import AsyncSessionLocal
from backend.db.models import (
    Approval,
    ApprovalDecision,
    Platform,
    Post,
    PostStatus,
)
from backend.orchestrator.state import CampaignWorkflowState

log = structlog.get_logger()

# ── Copy agent registry ───────────────────────────────────────────────────────

_COPY_AGENTS: dict[str, type[BaseCopyAgent]] = {
    Platform.linkedin.value:       LinkedInCopyAgent,
    Platform.blog.value:           BlogCopyAgent,
    Platform.instagram.value:      InstagramCopyAgent,
    Platform.xiaohongshu.value:    XiaohongshuCopyAgent,
    Platform.wechat_moments.value: WeChatMomentsAgent,
}

_MAX_COMPLIANCE_RETRIES = 2


# ── Helper ────────────────────────────────────────────────────────────────────

def _safe_uuid(s: Optional[str]) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(s) if s else None
    except (ValueError, AttributeError):
        return None


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def strategy_node(state: CampaignWorkflowState) -> dict:
    log.info("node_strategy", campaign_id=state["campaign_id"])
    try:
        inp   = StrategyInput(**state["strategy_input"])
        agent = StrategyAgent()
        async with AsyncSessionLocal() as db:
            output = await agent(inp, db=db)
        return {"strategy_output": output.model_dump(mode="json")}
    except Exception as exc:
        log.error("strategy_node_failed", error=str(exc))
        return {"errors": [f"strategy_node: {exc}"], "workflow_status": "failed"}


async def calendar_node(state: CampaignWorkflowState) -> dict:
    log.info("node_calendar", campaign_id=state["campaign_id"])
    try:
        from backend.agents.schemas.strategy import StrategyOutput

        strategy = StrategyOutput(**state["strategy_output"])
        inp_raw  = state["strategy_input"]

        inp = CalendarInput(
            campaign_id=uuid.UUID(state["campaign_id"]),
            strategy=strategy,
            start_date=inp_raw["start_date"],
            end_date=inp_raw["end_date"],
        )
        agent = CalendarAgent()
        async with AsyncSessionLocal() as db:
            output = await agent(inp, db=db)

        slots = output.model_dump(mode="json")["slots"]

        # Persist skeleton Post records so approvers can see them in the DB
        async with AsyncSessionLocal() as db:
            for slot in slots:
                post = Post(
                    id=uuid.UUID(slot["campaign_id"]) if False else uuid.uuid4(),
                    campaign_id=uuid.UUID(state["campaign_id"]),
                    platform=Platform(slot["platform"]),
                    scheduled_at=datetime.fromisoformat(slot["scheduled_at"]),
                    status=PostStatus.pending,
                    metadata_json={"working_title": slot["working_title"]},
                )
                db.add(post)
                slot["_post_db_id"] = str(post.id)
            await db.commit()

        return {"post_slots": slots}
    except Exception as exc:
        log.error("calendar_node_failed", error=str(exc))
        return {"errors": [f"calendar_node: {exc}"], "workflow_status": "failed"}


async def advance_post_node(state: CampaignWorkflowState) -> dict:
    """Pick the next slot and reset all per-post state."""
    idx   = state.get("current_slot_idx", 0)
    slots = state.get("post_slots", [])

    if idx >= len(slots):
        log.info("node_advance_post_done", processed=idx)
        return {"current_slot": None}

    slot = slots[idx]
    log.info("node_advance_post", idx=idx, platform=slot.get("platform"))
    return {
        "current_slot":           slot,
        "current_slot_idx":       idx + 1,
        "post_db_id":             slot.get("_post_db_id"),
        "copy_output":            None,
        "visual_output":          None,
        "compliance_output":      None,
        "compliance_feedback":    None,
        "compliance_retry_count": 0,
        "workflow_status":        "running",
    }


async def copy_node(state: CampaignWorkflowState) -> dict:
    slot     = state["current_slot"]
    platform = slot["platform"]
    feedback = state.get("compliance_feedback")
    log.info("node_copy", platform=platform, retry=state.get("compliance_retry_count", 0))

    try:
        agent_cls = _COPY_AGENTS.get(platform)
        if not agent_cls:
            raise ValueError(f"No copy agent for platform: {platform}")

        context = f"REVISION REQUIRED — previous compliance issues:\n{feedback}" if feedback else ""

        inp = CopyInput(
            post_id=_safe_uuid(state.get("post_db_id")) or uuid.uuid4(),
            campaign_id=uuid.UUID(state["campaign_id"]),
            platform=Platform(platform),
            pillar_name=slot["pillar_name"],
            working_title=slot["working_title"],
            content_brief=slot["content_brief"],
            campaign_context=context,
        )
        agent = agent_cls()
        async with AsyncSessionLocal() as db:
            output = await agent(inp, db=db)

        return {
            "copy_output":         output.model_dump(mode="json"),
            "compliance_feedback": None,  # clear after use
        }
    except Exception as exc:
        log.error("copy_node_failed", error=str(exc))
        return {"errors": [f"copy_node: {exc}"], "workflow_status": "failed"}


async def visual_node(state: CampaignWorkflowState) -> dict:
    slot = state["current_slot"]
    log.info("node_visual", platform=slot["platform"])

    try:
        copy_text = state["copy_output"]["copy"]
        inp = VisualInput(
            post_id=_safe_uuid(state.get("post_db_id")) or uuid.uuid4(),
            platform=Platform(slot["platform"]),
            copy=copy_text,
            pillar_name=slot["pillar_name"],
            content_brief=slot["content_brief"],
            generate_image=False,   # brief only; generation happens post-approval
        )
        agent = VisualAgent()
        async with AsyncSessionLocal() as db:
            output = await agent(inp, db=db)

        return {"visual_output": output.model_dump(mode="json")}
    except Exception as exc:
        log.error("visual_node_failed", error=str(exc))
        return {"errors": [f"visual_node: {exc}"], "workflow_status": "failed"}


async def compliance_node(state: CampaignWorkflowState) -> dict:
    slot = state["current_slot"]
    log.info("node_compliance", platform=slot["platform"])

    try:
        inp = ComplianceInput(
            post_id=_safe_uuid(state.get("post_db_id")) or uuid.uuid4(),
            platform=Platform(slot["platform"]),
            copy=state["copy_output"]["copy"],
        )
        agent = ComplianceAgent()
        async with AsyncSessionLocal() as db:
            output = await agent(inp, db=db)

        updates: dict = {"compliance_output": output.model_dump(mode="json")}

        if not output.passed:
            feedback = "; ".join(
                f"[{i.severity}] {i.category}: {i.description}"
                for i in output.issues
            )
            updates["compliance_retry_count"] = state.get("compliance_retry_count", 0) + 1
            updates["compliance_feedback"]    = feedback
            log.warning(
                "compliance_failed",
                retry_count=updates["compliance_retry_count"],
                issues=len(output.issues),
            )

        return updates
    except Exception as exc:
        log.error("compliance_node_failed", error=str(exc))
        return {"errors": [f"compliance_node: {exc}"], "workflow_status": "failed"}


async def approval_queue_node(state: CampaignWorkflowState) -> dict:
    """
    Saves the post as a draft and pauses the workflow for human review.

    Resumes when the API calls:
        Command(resume={"decision": "approved", "feedback": "..."})
    or:
        Command(resume={"decision": "rejected", "feedback": "..."})
    """
    post_id_str = state.get("post_db_id")
    copy        = state["copy_output"]["copy"]
    slot        = state["current_slot"]
    log.info("node_approval_queue", post_id=post_id_str, platform=slot["platform"])

    # Persist copy to the Post record and mark as draft
    post_uuid = _safe_uuid(post_id_str)
    if post_uuid:
        async with AsyncSessionLocal() as db:
            post = await db.get(Post, post_uuid)
            if post:
                post.copy            = copy
                post.status          = PostStatus.draft
                post.approval_status = ApprovalDecision.pending
                await db.commit()

        # Create the Approval record
        async with AsyncSessionLocal() as db:
            approval = Approval(
                post_id=post_uuid,
                reviewer="pending",
                decision=ApprovalDecision.pending,
            )
            db.add(approval)
            await db.commit()

    # ── Pause and wait for human decision ─────────────────────────────────────
    response = interrupt({
        "type":     "approval_required",
        "post_id":  post_id_str,
        "platform": slot["platform"],
        "copy":     copy,
        "message":  "Post is ready for review. Approve or reject via /api/v1/posts/{id}/approve.",
    })

    decision = "rejected"
    reviewer_feedback: Optional[str] = None
    if isinstance(response, dict):
        decision         = response.get("decision", "rejected")
        reviewer_feedback = response.get("feedback")
    elif isinstance(response, str):
        decision = response

    # Update the Approval record with the decision
    if post_uuid:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(Approval)
                .where(Approval.post_id == post_uuid)
                .order_by(Approval.timestamp.desc())
                .limit(1)
            )
            approval = result.scalar_one_or_none()
            if approval:
                approval.decision = (
                    ApprovalDecision.approved if decision == "approved"
                    else ApprovalDecision.rejected
                )
                approval.feedback = reviewer_feedback
                await db.commit()

    approved = decision == "approved"
    log.info("node_approval_decision", post_id=post_id_str, approved=approved)
    return {"workflow_status": "approved" if approved else "rejected"}


async def publishing_node(state: CampaignWorkflowState) -> dict:
    slot = state["current_slot"]
    log.info("node_publishing", platform=slot["platform"])

    try:
        visual_url = None
        if state.get("visual_output"):
            visual_url = state["visual_output"].get("image_url")

        inp = PublishInput(
            post_id=_safe_uuid(state.get("post_db_id")) or uuid.uuid4(),
            campaign_id=uuid.UUID(state["campaign_id"]),
            platform=Platform(slot["platform"]),
            copy=state["copy_output"]["copy"],
            visual_url=visual_url,
            scheduled_at=datetime.fromisoformat(slot["scheduled_at"]),
            metadata=state["copy_output"].get("metadata", {}),
        )
        agent = PublishingAgent()
        async with AsyncSessionLocal() as db:
            output = await agent(inp, db=db)

        completed = list(state.get("completed_post_ids", []))
        if state.get("post_db_id"):
            completed.append(state["post_db_id"])

        return {
            "workflow_status":    "completed",
            "completed_post_ids": completed,
        }
    except Exception as exc:
        log.error("publishing_node_failed", error=str(exc))
        return {"errors": [f"publishing_node: {exc}"]}


async def escalation_node(state: CampaignWorkflowState) -> dict:
    """
    Called when a post fails compliance after the maximum number of retries.
    Updates the post status in DB and records an error.
    """
    slot        = state["current_slot"]
    post_id_str = state.get("post_db_id")
    log.warning(
        "node_escalation",
        post_id=post_id_str,
        platform=slot["platform"],
        retries=state.get("compliance_retry_count", 0),
    )

    post_uuid = _safe_uuid(post_id_str)
    if post_uuid:
        async with AsyncSessionLocal() as db:
            post = await db.get(Post, post_uuid)
            if post:
                post.status = PostStatus.failed
                await db.commit()

    return {
        "workflow_status": "escalated",
        "errors": [
            f"Post {post_id_str} on {slot['platform']} escalated after "
            f"{_MAX_COMPLIANCE_RETRIES} compliance failures — manual review required"
        ],
    }
