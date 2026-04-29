"""
Post routes.

GET    /posts                      list (filterable, paginated)
GET    /posts/{id}                 detail
PATCH  /posts/{id}                 edit copy/visual/scheduled_at (creates PostVersion)
DELETE /posts/{id}                 delete
POST   /posts/{id}/approve         approve + resume workflow
POST   /posts/{id}/reject          reject + resume workflow
POST   /posts/{id}/schedule        set scheduled_at + mark as scheduled
POST   /posts/{id}/publish-now     publish immediately
POST   /posts/{id}/regenerate-copy   re-run CopyAgent
POST   /posts/{id}/regenerate-visual re-run VisualAgent
POST   /posts/{id}/run-compliance    re-run ComplianceAgent (async)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.api.schemas.post import (
    ApproveRequest,
    PostResponse,
    PostUpdate,
    PostVersionResponse,
    RegenerateCopyRequest,
    RejectRequest,
)
from backend.db.models import (
    Approval, ApprovalDecision, Post, PostStatus, PostVersion, User,
)

log    = structlog.get_logger()
router = APIRouter(prefix="/posts", tags=["posts"])


# ── rewrite on rejection ──────────────────────────────────────────────────────

async def _rewrite_post(post_id: uuid.UUID, feedback: str) -> None:
    """Re-run the copy agent with reviewer feedback, then re-queue for approval."""
    from backend.agents.copy.linkedin import LinkedInCopyAgent
    from backend.agents.copy.instagram import InstagramCopyAgent
    from backend.agents.copy.blog import BlogCopyAgent
    from backend.agents.copy.xiaohongshu import XiaohongshuCopyAgent
    from backend.agents.copy.wechat import WeChatMomentsAgent
    from backend.agents.schemas.copy import CopyInput
    from backend.db.database import AsyncSessionLocal

    agent_map = {
        "linkedin":       LinkedInCopyAgent,
        "instagram":      InstagramCopyAgent,
        "blog":           BlogCopyAgent,
        "xiaohongshu":    XiaohongshuCopyAgent,
        "wechat_moments": WeChatMomentsAgent,
    }

    async with AsyncSessionLocal() as db:
        post = await db.get(Post, post_id)
        if not post:
            return
        AgentClass = agent_map.get(post.platform.value)
        if not AgentClass:
            return

        meta = post.metadata_json or {}
        context = (
            f"REWRITE REQUESTED — Reviewer feedback:\n{feedback}\n\n"
            "Address this feedback specifically. Rewrite the copy to meet the reviewer's requirements."
        )
        inp = CopyInput(
            post_id=post_id,
            campaign_id=post.campaign_id,
            platform=post.platform,
            pillar_name=meta.get("pillar_name", ""),
            working_title=meta.get("working_title", ""),
            content_brief=meta.get("content_brief", ""),
            campaign_context=context,
        )
        try:
            result = await AgentClass()(inp, db=db)
            post.copy            = result.copy
            post.approval_status = ApprovalDecision.pending
            post.status          = PostStatus.draft
            db.add(Approval(
                post_id=post_id,
                reviewer="ai_rewrite",
                decision=ApprovalDecision.pending,
            ))
            await db.commit()
            log.info("post_rewritten", post_id=str(post_id))
        except Exception as exc:
            log.error("post_rewrite_failed", post_id=str(post_id), error=str(exc))


# ── GET /posts ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PostResponse], summary="List posts")
async def list_posts(
    campaign_id:      Optional[uuid.UUID] = Query(default=None),
    platform:         Optional[str]       = Query(default=None),
    status_filter:    Optional[str]       = Query(default=None, alias="status"),
    approval_status:  Optional[str]       = Query(default=None),
    scheduled_after:  Optional[str]       = Query(default=None),
    scheduled_before: Optional[str]       = Query(default=None),
    page:             int                 = Query(default=1, ge=1),
    page_size:        int                 = Query(default=20, ge=1, le=100),
    db:               AsyncSession        = Depends(get_db),
    _:                User                = Depends(get_current_user),
) -> list[PostResponse]:
    from backend.db.models import Platform as PlatformEnum, PostStatus as PS, ApprovalDecision as AD
    q = select(Post).order_by(Post.created_at.desc())
    if campaign_id:     q = q.where(Post.campaign_id == campaign_id)
    if platform:
        try:    q = q.where(Post.platform == PlatformEnum(platform))
        except ValueError: pass
    if status_filter:
        try:    q = q.where(Post.status == PS(status_filter))
        except ValueError: pass
    if approval_status:
        try:    q = q.where(Post.approval_status == AD(approval_status))
        except ValueError: pass
    skip = (page - 1) * page_size
    q = q.offset(skip).limit(page_size)
    result = await db.execute(q)
    return [PostResponse.model_validate(p) for p in result.scalars().all()]


# ── POST /posts ───────────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    campaign_id:  uuid.UUID
    platform:     str
    copy:         Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status:       str = "draft"


@router.post("", response_model=PostResponse, status_code=201, summary="Manually create a post")
async def create_post(
    body:         PostCreate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> PostResponse:
    from backend.db.models import Platform as PlatformEnum
    try:
        platform = PlatformEnum(body.platform)
    except ValueError:
        raise HTTPException(422, f"Unknown platform: {body.platform}")

    post = Post(
        id=uuid.uuid4(),
        campaign_id=body.campaign_id,
        platform=platform,
        copy=body.copy,
        scheduled_at=body.scheduled_at,
        status=PostStatus(body.status) if body.status in PostStatus._value2member_map_ else PostStatus.draft,
        metadata_json={"created_by": current_user.email},
    )
    db.add(post)
    await db.flush()
    log.info("post_created_manually", post_id=str(post.id), by=current_user.email)
    return PostResponse.model_validate(post)


# ── GET /posts/{id} ────────────────────────────────────────────────────────────

@router.get("/{post_id}", response_model=PostResponse, summary="Post detail")
async def get_post(
    post_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    _:       User         = Depends(get_current_user),
) -> PostResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    return PostResponse.model_validate(post)


# ── PATCH /posts/{id} ─────────────────────────────────────────────────────────

@router.patch("/{post_id}", response_model=PostResponse, summary="Edit post (creates version snapshot)")
async def update_post(
    post_id:      uuid.UUID,
    body:         PostUpdate,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> PostResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if post.approval_status == ApprovalDecision.approved:
        raise HTTPException(409, "Cannot edit an already-approved post")

    # Snapshot current state before mutation
    version_count_result = await db.execute(
        select(PostVersion).where(PostVersion.post_id == post_id)
    )
    current_version = len(version_count_result.scalars().all())
    snapshot = PostVersion(
        post_id=post_id,
        version_number=current_version + 1,
        copy=post.copy,
        visual_url=post.visual_url,
        scheduled_at=post.scheduled_at,
        edited_by=current_user.email,
    )
    db.add(snapshot)

    if body.copy          is not None: post.copy          = body.copy
    if body.visual_url    is not None: post.visual_url    = body.visual_url
    if body.scheduled_at  is not None: post.scheduled_at  = body.scheduled_at
    if body.metadata_json is not None: post.metadata_json = body.metadata_json
    await db.flush()
    return PostResponse.model_validate(post)


# ── DELETE /posts/{id} ────────────────────────────────────────────────────────

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Delete post")
async def delete_post(
    post_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    _:       User         = Depends(get_current_user),
) -> None:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    await db.delete(post)
    await db.flush()


# ── POST /posts/{id}/modify ───────────────────────────────────────────────────

class ModifyRequest(BaseModel):
    instructions: str


@router.post("/{post_id}/modify", response_model=PostResponse, summary="AI-rewrite post copy with instructions")
async def modify_post(
    post_id:      uuid.UUID,
    body:         ModifyRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> PostResponse:
    import anthropic
    from backend.config import settings
    from backend.prompts import load_prompt

    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if not post.copy:
        raise HTTPException(422, "Post has no copy to modify")
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured")

    try:
        brand_context = ""
        try:
            brand_context = load_prompt("brand_context")
        except Exception:
            pass

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            temperature=0.7,
            system=(
                f"You are a social media copywriter for Hexa Hub.\n\n"
                f"{brand_context}\n\n"
                "You will be given existing post copy and modification instructions. "
                "Return ONLY the rewritten copy — no explanation, no preamble, no quotes around it."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Platform: {post.platform.value}\n\n"
                    f"Current copy:\n{post.copy}\n\n"
                    f"Instructions: {body.instructions}\n\n"
                    "Rewrite the copy following the instructions exactly."
                ),
            }],
        )
        new_copy = message.content[0].text.strip()

        # Snapshot before overwriting
        version_result = await db.execute(select(PostVersion).where(PostVersion.post_id == post_id))
        current_version = len(version_result.scalars().all())
        db.add(PostVersion(
            post_id=post_id,
            version_number=current_version + 1,
            copy=post.copy,
            visual_url=post.visual_url,
            scheduled_at=post.scheduled_at,
            edited_by=f"ai_modify:{current_user.email}",
        ))

        post.copy = new_copy
        await db.flush()
        log.info("post_modified", post_id=str(post_id), by=current_user.email)
        return PostResponse.model_validate(post)

    except anthropic.APIError as e:
        raise HTTPException(502, f"Claude API error: {e}")


# ── POST /posts/{id}/schedule ────────────────────────────────────────────────

class ScheduleRequest(BaseModel):
    scheduled_at: datetime


@router.post("/{post_id}/schedule", response_model=PostResponse, summary="Schedule post for publishing")
async def schedule_post(
    post_id:      uuid.UUID,
    body:         ScheduleRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> PostResponse:
    from datetime import timezone
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if post.approval_status != ApprovalDecision.approved:
        raise HTTPException(409, "Post must be approved before scheduling")
    if body.scheduled_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(422, "scheduled_at must be in the future")

    post.scheduled_at = body.scheduled_at
    post.status       = PostStatus.scheduled
    await db.flush()

    log.info("post_scheduled", post_id=str(post_id), scheduled_at=body.scheduled_at.isoformat(),
             by=current_user.email)
    return PostResponse.model_validate(post)


# ── POST /posts/{id}/publish-now ──────────────────────────────────────────────

@router.post("/{post_id}/publish-now", response_model=PostResponse, summary="Publish post immediately")
async def publish_now(
    post_id:      uuid.UUID,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> PostResponse:
    from backend.services.scheduler import _publish_post
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if post.approval_status != ApprovalDecision.approved:
        raise HTTPException(409, "Post must be approved before publishing")
    if post.status == PostStatus.published:
        raise HTTPException(409, "Post is already published")

    await _publish_post(post, db)
    await db.commit()

    log.info("post_publish_now", post_id=str(post_id), by=current_user.email)
    return PostResponse.model_validate(post)


# ── POST /posts/{id}/approve ──────────────────────────────────────────────────

@router.post("/{post_id}/approve", response_model=PostResponse, summary="Approve post")
async def approve_post(
    post_id:      uuid.UUID,
    body:         ApproveRequest,
    db:           AsyncSession = Depends(get_db),
    current_user: User         = Depends(get_current_user),
) -> PostResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if post.approval_status != ApprovalDecision.pending:
        raise HTTPException(409, f"Post approval_status is '{post.approval_status.value}', expected 'pending'")

    post.approval_status = ApprovalDecision.approved
    post.status          = PostStatus.approved
    db.add(Approval(post_id=post_id, reviewer=current_user.email,
                    decision=ApprovalDecision.approved, feedback=body.feedback))
    await db.flush()

    log.info("post_approved", post_id=str(post_id), reviewer=current_user.email)
    return PostResponse.model_validate(post)


# ── POST /posts/{id}/reject ───────────────────────────────────────────────────

@router.post("/{post_id}/reject", response_model=PostResponse, summary="Reject post")
async def reject_post(
    post_id:          uuid.UUID,
    body:             RejectRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    current_user:     User         = Depends(get_current_user),
) -> PostResponse:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if post.approval_status != ApprovalDecision.pending:
        raise HTTPException(409, f"Post approval_status is '{post.approval_status.value}', expected 'pending'")

    post.approval_status = ApprovalDecision.rejected
    post.status          = PostStatus.rejected
    db.add(Approval(post_id=post_id, reviewer=current_user.email,
                    decision=ApprovalDecision.rejected, feedback=body.feedback))
    await db.flush()

    background_tasks.add_task(_rewrite_post, post_id, body.feedback)
    log.info("post_rejected", post_id=str(post_id), reviewer=current_user.email)
    return PostResponse.model_validate(post)


# ── POST /posts/{id}/regenerate-copy ─────────────────────────────────────────

@router.post("/{post_id}/regenerate-copy", response_model=dict,
             summary="Re-run CopyAgent for this post")
async def regenerate_copy(
    post_id:          uuid.UUID,
    body:             RegenerateCopyRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    current_user:     User         = Depends(get_current_user),
) -> dict:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")

    async def _regen():
        from backend.agents.copy.linkedin import LinkedInCopyAgent
        from backend.agents.copy.instagram import InstagramCopyAgent
        from backend.agents.copy.blog import BlogCopyAgent
        from backend.agents.copy.xiaohongshu import XiaohongshuCopyAgent
        from backend.agents.copy.wechat import WeChatMomentsAgent
        from backend.agents.schemas.copy import CopyInput
        from backend.db.database import AsyncSessionLocal
        from backend.db.models import Platform

        agent_map = {
            Platform.linkedin:       LinkedInCopyAgent,
            Platform.instagram:      InstagramCopyAgent,
            Platform.blog:           BlogCopyAgent,
            Platform.xiaohongshu:    XiaohongshuCopyAgent,
            Platform.wechat_moments: WeChatMomentsAgent,
        }
        AgentClass = agent_map.get(post.platform)
        if not AgentClass:
            return

        async with AsyncSessionLocal() as session:
            p = await session.get(Post, post_id)
            if not p:
                return
            inp = CopyInput(
                post_id=post_id,
                platform=p.platform,
                brief=body.override_prompt or p.metadata_json.get("brief", ""),
                pillar=p.metadata_json.get("pillar", ""),
                scheduled_at=p.scheduled_at,
            )
            result = await AgentClass()(inp, db=session)
            p.copy   = result.copy
            p.status = PostStatus.draft
            await session.commit()

    background_tasks.add_task(_regen)
    return {"message": "Copy regeneration queued", "post_id": str(post_id)}


# ── POST /posts/{id}/regenerate-visual ───────────────────────────────────────

@router.post("/{post_id}/regenerate-visual", response_model=dict,
             summary="Re-run VisualAgent for this post")
async def regenerate_visual(
    post_id:          uuid.UUID,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    _:                User         = Depends(get_current_user),
) -> dict:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")

    async def _regen():
        from backend.agents.visual import VisualAgent
        from backend.agents.schemas.visual import VisualInput
        from backend.db.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            p = await session.get(Post, post_id)
            if not p or not p.copy:
                return
            inp    = VisualInput(post_id=post_id, platform=p.platform, copy=p.copy)
            result = await VisualAgent()(inp, db=session)
            p.visual_url = result.visual_url
            await session.commit()

    background_tasks.add_task(_regen)
    return {"message": "Visual regeneration queued", "post_id": str(post_id)}


# ── POST /posts/{id}/run-compliance ──────────────────────────────────────────

@router.post("/{post_id}/run-compliance", response_model=dict,
             summary="Re-run ComplianceAgent (LLM-based, async)")
async def run_compliance(
    post_id:          uuid.UUID,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
    _:                User         = Depends(get_current_user),
) -> dict:
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(404, f"Post {post_id} not found")
    if not post.copy:
        raise HTTPException(422, "Post has no copy to check")

    async def _check():
        from backend.agents.compliance import ComplianceAgent
        from backend.agents.schemas.compliance import ComplianceInput
        from backend.db.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            p = await session.get(Post, post_id)
            if not p:
                return
            inp    = ComplianceInput(post_id=post_id, platform=p.platform, copy=p.copy or "")
            await ComplianceAgent()(inp, db=session)

    background_tasks.add_task(_check)
    return {"message": "Compliance check queued", "post_id": str(post_id)}


# ── GET /posts/{id}/versions ──────────────────────────────────────────────────

@router.get("/{post_id}/versions", response_model=list[PostVersionResponse],
            summary="Post edit history")
async def post_versions(
    post_id: uuid.UUID,
    db:      AsyncSession = Depends(get_db),
    _:       User         = Depends(get_current_user),
) -> list[PostVersionResponse]:
    result = await db.execute(
        select(PostVersion).where(PostVersion.post_id == post_id)
        .order_by(PostVersion.version_number.desc())
    )
    return [PostVersionResponse.model_validate(v) for v in result.scalars().all()]
