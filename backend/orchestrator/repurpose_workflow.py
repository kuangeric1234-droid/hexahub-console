"""
Repurpose workflow — takes one piece of content and generates platform-native
variants for all five platforms in parallel.

No LangGraph needed here: no human-in-loop, no compliance retry cycle.
Plain asyncio.gather runs all CopyAgents and VisualAgents concurrently.

Usage::

    from backend.orchestrator.repurpose_workflow import repurpose, RepurposeInput

    output = await repurpose(RepurposeInput(
        source_content="Long LinkedIn post...",
        source_platform="linkedin",
        target_platforms=["instagram", "xiaohongshu", "wechat_moments"],
        preserve_message="Hexa Hub cuts AU launch time from months to days.",
    ))
    # output.variants["instagram"] -> adapted Instagram copy
    # output.visual_briefs["instagram"] -> visual brief for that platform
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Literal, Optional

from pydantic import BaseModel

from backend.agents.copy import (
    BlogCopyAgent,
    InstagramCopyAgent,
    LinkedInCopyAgent,
    WeChatMomentsAgent,
    XiaohongshuCopyAgent,
)
from backend.agents.copy.base import BaseCopyAgent
from backend.agents.schemas.copy import CopyInput
from backend.agents.schemas.visual import VisualInput
from backend.agents.visual import VisualAgent
from backend.db.models import Platform


# ── Schemas ───────────────────────────────────────────────────────────────────

class RepurposeInput(BaseModel):
    source_content:   str
    source_platform:  Literal["blog", "linkedin", "instagram", "xiaohongshu", "wechat_moments", "raw"]
    target_platforms: list[Literal["linkedin", "blog", "instagram", "xiaohongshu", "wechat_moments"]]
    preserve_message: str        # core point that must survive across all variants
    campaign_id:      Optional[uuid.UUID] = None


class RepurposeOutput(BaseModel):
    source_platform:  str
    variants:         dict[str, str]   # platform → generated copy
    visual_briefs:    dict[str, str]   # platform → visual brief description
    errors:           dict[str, str]   # platform → error message (if any)


# ── Platform → agent mapping ──────────────────────────────────────────────────

_COPY_AGENTS: dict[str, type[BaseCopyAgent]] = {
    "linkedin":       LinkedInCopyAgent,
    "blog":           BlogCopyAgent,
    "instagram":      InstagramCopyAgent,
    "xiaohongshu":    XiaohongshuCopyAgent,
    "wechat_moments": WeChatMomentsAgent,
}

_MAX_BRIEF_CHARS = 1500   # truncate long source content in the brief field


# ── Worker function (one platform) ───────────────────────────────────────────

async def _generate_for_platform(
    inp:      RepurposeInput,
    platform: str,
) -> tuple[str, str, str | None]:
    """
    Returns (platform, copy, visual_brief_description) on success,
            (platform, error_str, None) on failure.
    """
    try:
        campaign_id = inp.campaign_id or uuid.uuid4()
        post_id     = uuid.uuid4()

        # ── Copy ─────────────────────────────────────────────────────────
        agent_cls = _COPY_AGENTS[platform]
        copy_inp  = CopyInput(
            post_id=post_id,
            campaign_id=campaign_id,
            platform=Platform(platform),
            pillar_name="Repurposed Content",
            working_title=inp.source_content[:80].strip(),
            content_brief=inp.source_content[:_MAX_BRIEF_CHARS],
            campaign_context=(
                f"Core message to preserve across all platforms: {inp.preserve_message}\n"
                f"Original platform: {inp.source_platform}. "
                "Adapt tone and format for this platform — do NOT copy verbatim."
            ),
        )
        copy_agent  = agent_cls()
        copy_output = await copy_agent(copy_inp)

        # ── Visual brief ─────────────────────────────────────────────────
        vis_inp = VisualInput(
            post_id=post_id,
            platform=Platform(platform),
            copy=copy_output.copy,
            pillar_name="Repurposed Content",
            content_brief=inp.source_content[:500],
            generate_image=False,
        )
        vis_agent  = VisualAgent()
        vis_output = await vis_agent(vis_inp)

        return platform, copy_output.copy, vis_output.visual_brief.description

    except Exception as exc:
        return platform, f"[Error: {exc}]", None


# ── Public entry point ────────────────────────────────────────────────────────

async def repurpose(inp: RepurposeInput) -> RepurposeOutput:
    """
    Run all target platforms concurrently and assemble the result.
    Failed platforms are included in output.errors rather than raising.
    """
    if not inp.target_platforms:
        return RepurposeOutput(
            source_platform=inp.source_platform,
            variants={},
            visual_briefs={},
            errors={},
        )

    tasks = [_generate_for_platform(inp, p) for p in inp.target_platforms]
    results = await asyncio.gather(*tasks)

    variants:      dict[str, str] = {}
    visual_briefs: dict[str, str] = {}
    errors:        dict[str, str] = {}

    for platform, content, visual in results:
        if content.startswith("[Error:"):
            errors[platform] = content
        else:
            variants[platform]      = content
            visual_briefs[platform] = visual or ""

    return RepurposeOutput(
        source_platform=inp.source_platform,
        variants=variants,
        visual_briefs=visual_briefs,
        errors=errors,
    )
