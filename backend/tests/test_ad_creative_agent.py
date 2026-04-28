"""
Unit tests for AdCreativeAgent.

Key concerns:
- Schema enforcement (variants have all required fields)
- Language-aware skill selection (Chinese → Chinese skills only, no Western bleed)
- Output parsing including recommended_test_priority clamping
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.agents.ad_creative import AdCreativeAgent, _WESTERN_SKILLS
from backend.agents.schemas.ad_creative import AdCreativeInput, AdCreativeOutput, AdVariant
from backend.llm.client import LLMProvider, LLMResponse


# ── fixtures ──────────────────────────────────────────────────────────────────

MOCK_EN_RESPONSE = {
    "variants": [
        {
            "headline": "Launch in Australia in 3 Days",
            "primary_text": "Most brands spend 3 months. Hexa Hub cuts it to 3 days.",
            "description": "Book a tour",
            "cta_button": "Learn More",
            "visual_brief": "Subject: warehouse floor Setting: Huntingdale Mood: operational Key element: hexagon signage Text overlay: '3 days to launch'",
            "rationale": "Problem-led: opens with the 3-month pain, flips to 3-day benefit.",
        },
        {
            "headline": "One Base. Five Functions.",
            "primary_text": "Fulfilment. Logistics. IT. Marketing. Retail. All at one address.",
            "description": "See how it works",
            "cta_button": "Learn More",
            "visual_brief": "Subject: overhead flat-lay of service icons Setting: white background Key element: hexagon Text overlay: 'Build locally. Scale sustainably.'",
            "rationale": "Benefit-led: leads with the integrated value prop.",
        },
        {
            "headline": "50+ Brands Already Operating",
            "primary_text": "Cross-border brands from China, South Korea, and the US chose Hexa Hub.",
            "description": "Join them",
            "cta_button": "Contact Us",
            "visual_brief": "Subject: diverse team Setting: modern operational space Mood: community Text overlay: none",
            "rationale": "Social proof: specific number, peer framing.",
        },
    ],
    "recommended_test_priority": [0, 2, 1],
    "targeting_notes": "Target Founder/COO by job title, company 10-200 people.",
}

MOCK_ZH_RESPONSE = {
    "variants": [
        {
            "headline": "在澳洲落地只要3天？",
            "primary_text": "真的。不是3个月，是3天。仓储、物流、IT、营销，一站搞定。",
            "description": None,
            "cta_button": "了解更多",
            "visual_brief": "Subject: warehouse interior with staff Setting: Huntingdale Mood: efficient, real Text overlay: '澳洲落地3天'",
            "rationale": "问题导向，种草风格，软性CTA。",
        }
    ],
    "recommended_test_priority": [0],
    "targeting_notes": "定向「跨境电商」「出海」兴趣标签。",
}


def _mock_llm(response_json: dict) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=LLMResponse(
        content=json.dumps(response_json),
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=800,
        output_tokens=600,
    ))
    return client


def _en_input(**kwargs) -> AdCreativeInput:
    return AdCreativeInput(
        platform="meta",
        objective="leads",
        product_or_offer="Hexa Hub — business infrastructure platform in Melbourne",
        audience="Cross-border e-commerce brands entering Australia",
        key_message="Launch operations in Australia in 3 days, not 3 months",
        cta="Book a tour",
        variants_count=3,
        language="en",
        **kwargs,
    )


def _zh_input(**kwargs) -> AdCreativeInput:
    return AdCreativeInput(
        platform="xiaohongshu",
        objective="awareness",
        product_or_offer="Hexa Hub — 澳洲一站式运营基地",
        audience="准备进入澳洲市场的中国跨境电商品牌",
        key_message="3天在澳洲落地运营",
        cta="了解更多",
        variants_count=1,
        language="zh-CN",
        **kwargs,
    )


# ── schema tests ──────────────────────────────────────────────────────────────

async def test_returns_ad_creative_output():
    agent  = AdCreativeAgent(llm_client=_mock_llm(MOCK_EN_RESPONSE))
    output = await agent(_en_input())
    assert isinstance(output, AdCreativeOutput)


async def test_variants_match_expected_count():
    agent  = AdCreativeAgent(llm_client=_mock_llm(MOCK_EN_RESPONSE))
    output = await agent(_en_input())
    assert len(output.variants) == 3


async def test_each_variant_has_required_fields():
    agent  = AdCreativeAgent(llm_client=_mock_llm(MOCK_EN_RESPONSE))
    output = await agent(_en_input())
    for variant in output.variants:
        assert isinstance(variant, AdVariant)
        assert variant.headline
        assert variant.primary_text
        assert variant.cta_button
        assert variant.visual_brief
        assert variant.rationale


async def test_recommended_test_priority_indices_are_valid():
    agent  = AdCreativeAgent(llm_client=_mock_llm(MOCK_EN_RESPONSE))
    output = await agent(_en_input())
    n = len(output.variants)
    assert all(0 <= i < n for i in output.recommended_test_priority)


async def test_out_of_range_priority_indices_are_clamped():
    bad_response = {**MOCK_EN_RESPONSE, "recommended_test_priority": [0, 1, 99, -1]}
    agent  = AdCreativeAgent(llm_client=_mock_llm(bad_response))
    output = await agent(_en_input())
    n = len(output.variants)
    assert all(0 <= i < n for i in output.recommended_test_priority)


async def test_targeting_notes_present():
    agent  = AdCreativeAgent(llm_client=_mock_llm(MOCK_EN_RESPONSE))
    output = await agent(_en_input())
    assert output.targeting_notes


# ── skill selection tests ─────────────────────────────────────────────────────

def test_english_request_loads_western_skills():
    agent     = AdCreativeAgent()
    inp       = _en_input()
    skill_str = agent._load_skills_context(inp)
    # Should load western skills
    for skill in ["ad-creative", "paid-ads", "copywriting", "marketing-psychology"]:
        assert f"# Skill: {skill}" in skill_str, f"Expected {skill} in EN skills context"


def test_xhs_chinese_request_loads_xhs_skill_only():
    agent     = AdCreativeAgent()
    inp       = _zh_input(platform="xiaohongshu")
    skill_str = agent._load_skills_context(inp)
    assert "xiaohongshu" in skill_str.lower() or "种草" in skill_str
    # Western skills must NOT appear
    for western in ["ad-creative", "paid-ads", "copywriting"]:
        assert f"# Skill: {western}" not in skill_str, (
            f"Western skill '{western}' must not appear in XHS zh-CN context"
        )


def test_wechat_chinese_request_loads_wechat_skill_only():
    agent     = AdCreativeAgent()
    inp       = _zh_input(platform="wechat")
    skill_str = agent._load_skills_context(inp)
    assert "wechat" in skill_str.lower() or "朋友圈" in skill_str
    for western in ["ad-creative", "paid-ads", "copywriting"]:
        assert f"# Skill: {western}" not in skill_str


def test_chinese_non_platform_specific_returns_empty_skills():
    """zh-CN on 'meta' or 'google' → no matching custom skill → empty string."""
    agent     = AdCreativeAgent()
    inp       = AdCreativeInput(
        platform="google", objective="leads",
        product_or_offer="test", audience="test", key_message="test",
        cta="test", language="zh-CN",
    )
    skill_str = agent._load_skills_context(inp)
    assert skill_str == ""


def test_none_input_falls_back_to_required_skills():
    """Called with no input (e.g. from estimate_prompt_tokens) → use class-level skills."""
    agent     = AdCreativeAgent()
    skill_str = agent._load_skills_context(None)
    assert "# Skill: ad-creative" in skill_str


# ── system prompt assembly ────────────────────────────────────────────────────

def test_en_system_prompt_contains_skills_before_agent_prompt():
    agent       = AdCreativeAgent()
    inp         = _en_input()
    agent_prompt = "AGENT PROMPT PLACEHOLDER"
    prompt       = agent._build_system_prompt(agent_prompt, inp)
    skill_pos   = prompt.index("# Skill: ad-creative")
    agent_pos   = prompt.index(agent_prompt)
    assert skill_pos < agent_pos


async def test_zh_xhs_run_does_not_call_with_western_skills(monkeypatch):
    captured_prompts: list[str] = []

    async def fake_complete(system_prompt, user_prompt, **kwargs):
        captured_prompts.append(system_prompt)
        return LLMResponse(
            content=json.dumps(MOCK_ZH_RESPONSE),
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            input_tokens=400,
            output_tokens=300,
        )

    agent = AdCreativeAgent()
    agent.llm = AsyncMock()
    agent.llm.complete = fake_complete

    await agent(_zh_input(platform="xiaohongshu"))

    assert len(captured_prompts) == 1
    system_prompt = captured_prompts[0]
    for western in ["# Skill: ad-creative", "# Skill: paid-ads", "# Skill: copywriting"]:
        assert western not in system_prompt, (
            f"Western skill '{western}' must not appear in XHS zh-CN system prompt"
        )
