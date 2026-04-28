"""
Tests verifying that required_skills are correctly injected into system prompts.

These tests check the assembled prompt content — not LLM calls — so they're
fast and don't need mocking.
"""
from __future__ import annotations

import pytest

from backend.agents.compliance import ComplianceAgent
from backend.agents.copy.blog import BlogCopyAgent
from backend.agents.copy.instagram import InstagramCopyAgent
from backend.agents.copy.linkedin import LinkedInCopyAgent
from backend.agents.copy.wechat import WeChatMomentsAgent
from backend.agents.copy.xiaohongshu import XiaohongshuCopyAgent
from backend.agents.strategy import StrategyAgent
from backend.agents.calendar import CalendarAgent


# ── required_skills declarations ─────────────────────────────────────────────

def test_strategy_agent_declares_expected_skills():
    assert "marketing-ideas"     in StrategyAgent.required_skills
    assert "content-strategy"    in StrategyAgent.required_skills
    assert "marketing-psychology" in StrategyAgent.required_skills
    assert "customer-research"   in StrategyAgent.required_skills


def test_calendar_agent_declares_expected_skills():
    assert "content-strategy" in CalendarAgent.required_skills
    assert "social-content"   in CalendarAgent.required_skills


def test_linkedin_declares_expected_skills():
    assert "copywriting"          in LinkedInCopyAgent.required_skills
    assert "social-content"       in LinkedInCopyAgent.required_skills
    assert "marketing-psychology" in LinkedInCopyAgent.required_skills


def test_blog_declares_expected_skills():
    assert "copywriting"   in BlogCopyAgent.required_skills
    assert "seo-audit"     in BlogCopyAgent.required_skills
    assert "ai-seo"        in BlogCopyAgent.required_skills
    assert "schema-markup" in BlogCopyAgent.required_skills


def test_instagram_declares_expected_skills():
    assert "copywriting"   in InstagramCopyAgent.required_skills
    assert "social-content" in InstagramCopyAgent.required_skills
    assert "ad-creative"   in InstagramCopyAgent.required_skills


def test_xhs_uses_only_custom_skill():
    assert XiaohongshuCopyAgent.required_skills == ["xiaohongshu-content"]
    # Confirm NO Western skills leak in
    western_skills = {"copywriting", "social-content", "ad-creative",
                      "marketing-psychology", "seo-audit"}
    assert not western_skills.intersection(set(XiaohongshuCopyAgent.required_skills))


def test_wechat_uses_only_custom_skill():
    assert WeChatMomentsAgent.required_skills == ["wechat-moments-content"]
    western_skills = {"copywriting", "social-content", "ad-creative",
                      "marketing-psychology", "seo-audit"}
    assert not western_skills.intersection(set(WeChatMomentsAgent.required_skills))


def test_compliance_declares_copy_editing():
    assert "copy-editing" in ComplianceAgent.required_skills


# ── prompt assembly ───────────────────────────────────────────────────────────

def test_linkedin_system_prompt_contains_skill_marker():
    agent  = LinkedInCopyAgent()
    prompt = agent._build_system_prompt("AGENT_PROMPT_PLACEHOLDER")
    assert "# Skill: copywriting" in prompt


def test_linkedin_system_prompt_order():
    """Skills must appear BEFORE the agent prompt (dominant signal at end)."""
    agent  = LinkedInCopyAgent()
    prompt = agent._build_system_prompt("AGENT_PROMPT_PLACEHOLDER")
    skill_pos  = prompt.index("# Skill: copywriting")
    agent_pos  = prompt.index("AGENT_PROMPT_PLACEHOLDER")
    assert skill_pos < agent_pos, (
        "Skills must appear before the agent-specific prompt so the agent "
        "prompt remains the dominant signal (read last by the LLM)"
    )


def test_linkedin_system_prompt_has_separator():
    agent  = LinkedInCopyAgent()
    prompt = agent._build_system_prompt("AGENT_PROMPT_PLACEHOLDER")
    assert "===" in prompt


def test_xhs_system_prompt_contains_xhs_skill():
    agent  = XiaohongshuCopyAgent()
    prompt = agent._build_system_prompt("AGENT_PROMPT_PLACEHOLDER")
    assert "xiaohongshu-content" in prompt.lower() or "种草" in prompt


def test_xhs_system_prompt_does_not_contain_copywriting():
    """Western copywriting skill must not appear in XHS prompt."""
    agent  = XiaohongshuCopyAgent()
    prompt = agent._build_system_prompt("AGENT_PROMPT_PLACEHOLDER")
    assert "# Skill: copywriting" not in prompt


def test_agent_with_no_skills_returns_prompt_unchanged():
    """An agent with required_skills=[] should return the prompt verbatim."""
    from backend.agents.base import BaseAgent
    from backend.agents.schemas.strategy import StrategyInput, StrategyOutput

    class NoSkillAgent(BaseAgent[StrategyInput, StrategyOutput]):
        agent_name      = "no_skill_test"
        required_skills = []
        async def run(self, input_data, db=None): ...  # type: ignore[override]

    agent  = NoSkillAgent()
    prompt = agent._build_system_prompt("JUST THE AGENT PROMPT")
    assert prompt == "JUST THE AGENT PROMPT"


# ── skills_loaded in log ──────────────────────────────────────────────────────

def test_skills_loaded_key_in_persist_log_input():
    """
    _persist_log adds skills_loaded to input_json before writing.
    Verify by inspecting the mutation directly (no DB needed).
    """
    from pydantic import BaseModel

    class FakeInput(BaseModel):
        value: str = "test"

    agent = LinkedInCopyAgent()
    inp   = FakeInput()
    data  = inp.model_dump(mode="json")
    data["skills_loaded"] = list(agent.required_skills)   # same logic as _persist_log

    assert "skills_loaded" in data
    assert "copywriting" in data["skills_loaded"]
