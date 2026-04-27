"""
Unit tests for all 5 CopyAgents.

Each agent is tested for:
- Returns CopyOutput with correct platform
- Platform-specific metadata extraction
- Limit warnings when copy exceeds/falls short of target
- LLM is called exactly once per run
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from backend.agents.copy import (
    BlogCopyAgent,
    InstagramCopyAgent,
    LinkedInCopyAgent,
    WeChatMomentsAgent,
    XiaohongshuCopyAgent,
)
from backend.agents.schemas.copy import CopyInput, CopyOutput
from backend.db.models import Platform
from tests.conftest import make_mock_llm

# ── shared fixtures ───────────────────────────────────────────────────────────

def _make_input(platform: Platform, **kwargs) -> CopyInput:
    return CopyInput(
        post_id=uuid4(),
        campaign_id=uuid4(),
        platform=platform,
        pillar_name="Operations",
        working_title="Inside Hexa Hub's fulfilment floor",
        content_brief="Show how integrated ops reduce time-to-dispatch for cross-border brands.",
        target_audience="Cross-border e-commerce brands entering AU",
        **kwargs,
    )


# ── LinkedIn ──────────────────────────────────────────────────────────────────

LINKEDIN_COPY = (
    "Most brands entering Australia spend 3 months finding a warehouse.\n\n"
    "We cut that to 3 days.\n\n"
    "At Hexa Hub, the infrastructure is already running: fulfilment, IT, marketing — "
    "all under one roof at 7 Distribution Circuit, Huntingdale.\n\n"
    "The question isn't whether you need a base. It's whether you can afford to build one from scratch.\n\n"
    "Message us to see the floor."
)


async def test_linkedin_returns_copy_output():
    agent  = LinkedInCopyAgent(llm_client=make_mock_llm(LINKEDIN_COPY))
    output = await agent(_make_input(Platform.linkedin))
    assert isinstance(output, CopyOutput)
    assert output.platform == Platform.linkedin


async def test_linkedin_extracts_hook_line():
    agent  = LinkedInCopyAgent(llm_client=make_mock_llm(LINKEDIN_COPY))
    output = await agent(_make_input(Platform.linkedin))
    assert output.metadata.get("hook_line") == "Most brands entering Australia spend 3 months finding a warehouse."


async def test_linkedin_warns_when_over_1300_chars():
    long_copy = "A" * 1400
    agent     = LinkedInCopyAgent(llm_client=make_mock_llm(long_copy))
    output    = await agent(_make_input(Platform.linkedin))
    assert any("1300" in w for w in output.warnings)


async def test_linkedin_no_warning_within_limit():
    short_copy = LINKEDIN_COPY  # 401 chars — well within 1300
    agent      = LinkedInCopyAgent(llm_client=make_mock_llm(short_copy))
    output     = await agent(_make_input(Platform.linkedin))
    assert not output.warnings


# ── Blog ─────────────────────────────────────────────────────────────────────

BLOG_COPY = """Meta description: How Hexa Hub's integrated infrastructure cuts launch time for cross-border brands entering Australia.

# Inside Hexa Hub's Fulfilment Floor

Most brands entering Australia underestimate how long it takes to set up operations.

## The fragmented operations problem

Fragmented logistics, separate IT, disconnected marketing — each adds weeks.

## What integrated infrastructure looks like

At 7 Distribution Circuit, Huntingdale, every system is already running.

### Fulfilment and dispatch

Same-day dispatch is the baseline, not the aspiration.

## Key takeaways
- Integrated ops cut time-to-launch by weeks
- Co-located logistics, IT and marketing reduce vendor friction
- Hexa Hub's model is access, not ownership

Book a tour to see the floor in action.
""" * 5  # repeat to hit word count


async def test_blog_returns_copy_output():
    agent  = BlogCopyAgent(llm_client=make_mock_llm(BLOG_COPY))
    output = await agent(_make_input(Platform.blog))
    assert output.platform == Platform.blog


async def test_blog_extracts_headings():
    agent  = BlogCopyAgent(llm_client=make_mock_llm(BLOG_COPY))
    output = await agent(_make_input(Platform.blog))
    headings = output.metadata.get("headings", [])
    assert len(headings) >= 2
    assert any("fulfilment" in h.lower() or "Fulfilment" in h for h in headings)


async def test_blog_extracts_meta_description():
    agent  = BlogCopyAgent(llm_client=make_mock_llm(BLOG_COPY))
    output = await agent(_make_input(Platform.blog))
    meta   = output.metadata.get("meta_description", "")
    assert "Hexa Hub" in meta or len(meta) > 10


async def test_blog_warns_if_too_short():
    short_blog = "This is a very short blog post. " * 20  # ~100 words
    agent      = BlogCopyAgent(llm_client=make_mock_llm(short_blog))
    output     = await agent(_make_input(Platform.blog))
    assert any("1200" in w for w in output.warnings)


# ── Instagram ─────────────────────────────────────────────────────────────────

INSTAGRAM_COPY = (
    "Operations that actually work. 📦\n\n"
    "Three brands. One building. Zero wasted hours.\n\n"
    "That's what integrated infrastructure looks like at Hexa Hub, Huntingdale.\n\n"
    "DM us to see it.\n\n"
    "#hexahub #hexahubau #australiabusiness #crossborderecommerce #ecommerceaustralia "
    "#businessinfrastructure #melbournebusiness"
)


async def test_instagram_extracts_hashtags():
    agent  = InstagramCopyAgent(llm_client=make_mock_llm(INSTAGRAM_COPY))
    output = await agent(_make_input(Platform.instagram))
    tags   = output.metadata.get("hashtags", [])
    assert len(tags) >= 5
    assert "#hexahub" in tags


async def test_instagram_warns_too_few_hashtags():
    copy_no_tags = "Great post with no hashtags."
    agent        = InstagramCopyAgent(llm_client=make_mock_llm(copy_no_tags))
    output       = await agent(_make_input(Platform.instagram))
    assert any("hashtag" in w.lower() for w in output.warnings)


async def test_instagram_hashtag_count_in_metadata():
    agent  = InstagramCopyAgent(llm_client=make_mock_llm(INSTAGRAM_COPY))
    output = await agent(_make_input(Platform.instagram))
    assert output.metadata.get("hashtag_count") == len(output.metadata.get("hashtags", []))


# ── Xiaohongshu ───────────────────────────────────────────────────────────────

XHS_COPY = (
    "在澳洲开仓库，我们只花了3天 🏭\n\n"
    "很多跨境品牌告诉我，在澳洲找仓库、搭物流、配IT少说要3个月。\n"
    "但我们在Hexa Hub Huntingdale落地的时候，3天就开始运营了。\n\n"
    "这里不是普通的共享办公——而是一个真正意义上的一站式运营基地：\n"
    "✅ 仓储+物流+IT+营销，全在一栋楼里\n"
    "✅ 中英文双语团队，沟通无障碍\n"
    "✅ 按需扩展，不用签长期合同\n\n"
    "如果你也在考虑澳洲市场，欢迎来实地看看 👇\n\n"
    "#澳洲电商 #跨境出海 #hexahub #澳洲仓储 #品牌出海澳洲"
)


async def test_xhs_extracts_topic_tags():
    agent  = XiaohongshuCopyAgent(llm_client=make_mock_llm(XHS_COPY))
    output = await agent(_make_input(Platform.xiaohongshu))
    tags   = output.metadata.get("topic_tags", [])
    assert len(tags) >= 3
    assert "#澳洲电商" in tags or "#hexahub" in tags


async def test_xhs_metadata_language_is_zh():
    agent  = XiaohongshuCopyAgent(llm_client=make_mock_llm(XHS_COPY))
    output = await agent(_make_input(Platform.xiaohongshu))
    assert output.metadata.get("language") == "zh"


async def test_xhs_warns_if_no_chinese():
    english_only = "This is entirely in English with #somehashtag"
    agent        = XiaohongshuCopyAgent(llm_client=make_mock_llm(english_only))
    output       = await agent(_make_input(Platform.xiaohongshu))
    assert any("Chinese" in w for w in output.warnings)


async def test_xhs_warns_if_no_topic_tags():
    no_tags = "在澳洲落地运营不难，找对平台就行。欢迎来Hexa Hub参观。"
    agent   = XiaohongshuCopyAgent(llm_client=make_mock_llm(no_tags))
    output  = await agent(_make_input(Platform.xiaohongshu))
    assert any("tag" in w.lower() or "话题" in w for w in output.warnings)


# ── WeChat Moments ────────────────────────────────────────────────────────────

WECHAT_COPY = "今天带团队参观了Huntingdale的仓库，3000平方米全自动化，跨境电商真的可以做到当天发货。有兴趣的朋友私信我。"


async def test_wechat_returns_copy_within_limit():
    agent  = WeChatMomentsAgent(llm_client=make_mock_llm(WECHAT_COPY))
    output = await agent(_make_input(Platform.wechat_moments))
    assert len(output.copy) <= 150


async def test_wechat_truncates_overlong_copy():
    long_copy = "这是一条非常非常非常非常非常非常非常非常非常非常长的微信朋友圈文案，" * 5
    agent     = WeChatMomentsAgent(llm_client=make_mock_llm(long_copy))
    output    = await agent(_make_input(Platform.wechat_moments))
    assert len(output.copy) <= 150
    assert any("truncat" in w.lower() or "150" in w for w in output.warnings)


async def test_wechat_no_warning_for_short_copy():
    agent  = WeChatMomentsAgent(llm_client=make_mock_llm(WECHAT_COPY))
    output = await agent(_make_input(Platform.wechat_moments))
    assert not output.warnings


async def test_wechat_metadata_has_char_limit():
    agent  = WeChatMomentsAgent(llm_client=make_mock_llm(WECHAT_COPY))
    output = await agent(_make_input(Platform.wechat_moments))
    assert output.metadata.get("char_limit") == 150


# ── common across all agents ──────────────────────────────────────────────────

@pytest.mark.parametrize("AgentClass,platform,copy", [
    (LinkedInCopyAgent,  Platform.linkedin,       LINKEDIN_COPY),
    (InstagramCopyAgent, Platform.instagram,      INSTAGRAM_COPY),
    (XiaohongshuCopyAgent, Platform.xiaohongshu, XHS_COPY),
    (WeChatMomentsAgent, Platform.wechat_moments, WECHAT_COPY),
])
async def test_copy_output_post_id_matches_input(AgentClass, platform, copy):
    inp    = _make_input(platform)
    agent  = AgentClass(llm_client=make_mock_llm(copy))
    output = await agent(inp)
    assert output.post_id == inp.post_id


@pytest.mark.parametrize("AgentClass,platform,copy", [
    (LinkedInCopyAgent,  Platform.linkedin,       LINKEDIN_COPY),
    (BlogCopyAgent,      Platform.blog,           BLOG_COPY),
    (InstagramCopyAgent, Platform.instagram,      INSTAGRAM_COPY),
    (XiaohongshuCopyAgent, Platform.xiaohongshu, XHS_COPY),
    (WeChatMomentsAgent, Platform.wechat_moments, WECHAT_COPY),
])
async def test_llm_called_once_per_run(AgentClass, platform, copy):
    mock   = make_mock_llm(copy)
    agent  = AgentClass(llm_client=mock)
    await agent(_make_input(platform))
    mock.complete.assert_awaited_once()
