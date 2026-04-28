"""
SkillLoader — loads marketing skill markdown files for injection into agent
system prompts.

Search order (first match wins):
  1. backend/skills/custom/{skill_name}.md    ← project-specific overrides
  2. backend/skills/marketing_external/skills/{skill_name}/SKILL.md

Custom files override external skills of the same name.  This is the
localization mechanism: drop a `copywriting.md` in custom/ to replace
the Western-focused external version for any agent that needs it.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillNotFoundError(Exception):
    pass


class SkillLoader:
    # Resolved relative to this file so CWD doesn't matter
    _BASE = Path(__file__).parent
    EXTERNAL_BASE = _BASE / "marketing_external" / "skills"
    CUSTOM_BASE   = _BASE / "custom"

    @lru_cache(maxsize=128)
    def load(self, skill_name: str) -> str:
        """Load a single skill's content. Result is cached after first read."""
        custom_path = self.CUSTOM_BASE / f"{skill_name}.md"
        if custom_path.exists():
            logger.info("Loaded custom skill: %s", skill_name)
            return custom_path.read_text(encoding="utf-8")

        external_path = self.EXTERNAL_BASE / skill_name / "SKILL.md"
        if external_path.exists():
            logger.info("Loaded external skill: %s", skill_name)
            return external_path.read_text(encoding="utf-8")

        raise SkillNotFoundError(
            f"Skill '{skill_name}' not found in custom ({self.CUSTOM_BASE}) "
            f"or external ({self.EXTERNAL_BASE / skill_name}) directories"
        )

    def load_many(self, skill_names: list[str]) -> str:
        """
        Load multiple skills and return them as a single concatenated block.
        Missing skills are logged as warnings and skipped — never crash the agent.
        """
        if not skill_names:
            return ""

        sections: list[str] = []
        for name in skill_names:
            try:
                content = self.load(name)
                sections.append(f"# Skill: {name}\n\n{content}")
            except SkillNotFoundError as exc:
                logger.warning(str(exc))

        return "\n\n---\n\n".join(sections)

    def list_available(self) -> dict[str, list[str]]:
        """Return all discoverable skills, separated by source."""
        external: list[str] = []
        if self.EXTERNAL_BASE.exists():
            external = sorted(
                p.name for p in self.EXTERNAL_BASE.iterdir()
                if p.is_dir() and (p / "SKILL.md").exists()
            )

        custom: list[str] = []
        if self.CUSTOM_BASE.exists():
            custom = sorted(
                p.stem for p in self.CUSTOM_BASE.glob("*.md")
                if p.stem.upper() != "README"
            )

        return {"external": external, "custom": custom}

    def clear_cache(self) -> None:
        """Invalidate the in-process cache (e.g. after skill files are updated)."""
        self.load.cache_clear()


# Module-level singleton — import this everywhere
skill_loader = SkillLoader()
