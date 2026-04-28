"""
Tests for SkillLoader.

These tests read actual files from the submodule and custom/ directory
so they verify real content, not mocks.
"""
from __future__ import annotations

import pytest
from pathlib import Path

from backend.skills.loader import SkillLoader, SkillNotFoundError


@pytest.fixture
def loader():
    l = SkillLoader()
    l.clear_cache()
    return l


# ── external skills ───────────────────────────────────────────────────────────

def test_load_external_skill_copywriting(loader):
    content = loader.load("copywriting")
    assert len(content) > 100
    # The word "copywriting" or "copy" should appear somewhere in the file
    assert "copy" in content.lower()


def test_load_external_skill_social_content(loader):
    content = loader.load("social-content")
    assert len(content) > 100


def test_load_external_skill_seo_audit(loader):
    content = loader.load("seo-audit")
    assert len(content) > 100


# ── custom skills ─────────────────────────────────────────────────────────────

def test_load_custom_xhs_skill(loader):
    content = loader.load("xiaohongshu-content")
    assert "种草" in content or "Xiaohongshu" in content


def test_load_custom_wechat_skill(loader):
    content = loader.load("wechat-moments-content")
    assert "朋友圈" in content or "WeChat" in content


# ── override: custom beats external ──────────────────────────────────────────

def test_custom_overrides_external(tmp_path, monkeypatch, loader):
    custom_dir = tmp_path / "custom"
    custom_dir.mkdir()
    (custom_dir / "copywriting.md").write_text("CUSTOM OVERRIDE CONTENT", encoding="utf-8")

    monkeypatch.setattr(loader, "CUSTOM_BASE", custom_dir)
    loader.clear_cache()

    content = loader.load("copywriting")
    assert content == "CUSTOM OVERRIDE CONTENT"


# ── missing skill ─────────────────────────────────────────────────────────────

def test_missing_skill_raises_skill_not_found(loader):
    with pytest.raises(SkillNotFoundError, match="does-not-exist"):
        loader.load("does-not-exist")


# ── load_many ─────────────────────────────────────────────────────────────────

def test_load_many_returns_concatenated_content(loader):
    result = loader.load_many(["copywriting", "social-content"])
    assert "# Skill: copywriting" in result
    assert "# Skill: social-content" in result
    assert "---" in result  # separator between skills


def test_load_many_skips_missing_skill(loader):
    result = loader.load_many(["copywriting", "does-not-exist-skill", "social-content"])
    assert "# Skill: copywriting" in result
    assert "# Skill: social-content" in result
    assert "does-not-exist-skill" not in result


def test_load_many_empty_list_returns_empty_string(loader):
    assert loader.load_many([]) == ""


def test_load_many_all_missing_returns_empty_string(loader):
    result = loader.load_many(["fake-a", "fake-b"])
    assert result == ""


# ── list_available ────────────────────────────────────────────────────────────

def test_list_available_has_external_and_custom_keys(loader):
    available = loader.list_available()
    assert "external" in available
    assert "custom" in available


def test_list_available_external_has_expected_skills(loader):
    available = loader.list_available()
    assert "copywriting" in available["external"]
    assert "seo-audit"   in available["external"]
    assert "social-content" in available["external"]
    assert len(available["external"]) >= 30


def test_list_available_custom_includes_placeholders(loader):
    available = loader.list_available()
    assert "xiaohongshu-content"    in available["custom"]
    assert "wechat-moments-content" in available["custom"]


# ── caching ───────────────────────────────────────────────────────────────────

def test_cache_is_populated_on_second_load(loader):
    loader.load("copywriting")
    info = loader.load.cache_info()
    assert info.currsize >= 1

    loader.load("copywriting")   # second load should hit cache
    info2 = loader.load.cache_info()
    assert info2.hits >= 1


def test_clear_cache_resets_cache(loader):
    loader.load("copywriting")
    loader.clear_cache()
    info = loader.load.cache_info()
    assert info.currsize == 0
