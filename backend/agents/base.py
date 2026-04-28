"""
BaseAgent — abstract foundation for all specialist agents.

Every subclass must set `agent_name` and implement `run()`.
Optionally override `validate()` for pre-run input checks.

Calling an agent::

    agent  = StrategyAgent()
    output = await agent(input_data, db=db_session)

The `__call__` wrapper handles: validate → run → structured log → re-raise.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AgentLog, AgentLogStatus
from backend.llm.client import LLMClient, LLMProvider
from backend.skills.loader import skill_loader

log = structlog.get_logger()

InputT  = TypeVar("InputT",  bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

_SKILLS_HEADER = (
    "# MARKETING SKILLS CONTEXT\n\n"
    "The following marketing expertise is provided as supporting knowledge "
    "to inform your output quality. Apply it where relevant.\n\n"
)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    # ── class-level config (override in subclasses) ───────────────────────────
    agent_name:       str           # required — set on every subclass
    default_provider: LLMProvider = LLMProvider.ANTHROPIC
    default_model:    Optional[str] = None
    required_skills:  list[str]   = []  # skill names injected into system prompt

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm  = llm_client or LLMClient(
            provider=self.default_provider,
            model=self.default_model,
        )
        self._log = log.bind(agent=self.agent_name)

    # ── skill injection ───────────────────────────────────────────────────────

    def _load_skills_context(self, input_data: Any = None) -> str:
        """
        Return the loaded skill content block for the current run.

        Override in subclasses that need input-aware skill selection
        (e.g. AdCreativeAgent selects skills by language/platform).
        The default returns skill_loader.load_many(self.required_skills).
        """
        return skill_loader.load_many(self.required_skills)

    def _build_system_prompt(self, agent_prompt_content: str, input_data: Any = None) -> str:
        """
        Assemble the final system prompt.

        Order
        -----
        1. Marketing skills context  (_load_skills_context — supporting knowledge)
        2. Agent-specific prompt     (brand context + task instructions — dominant signal)

        The agent prompt closes the system context so its task instructions
        are read last and remain the dominant signal for the LLM.
        Agents whose _load_skills_context returns "" get the prompt unchanged.

        Parameters
        ----------
        agent_prompt_content
            The raw text from the agent's prompts/*.md file.
        input_data
            Optional — passed to _load_skills_context for agents that select
            skills based on request properties (language, platform, etc.).
        """
        skill_block = self._load_skills_context(input_data)
        if not skill_block:
            return agent_prompt_content
        return (
            f"{_SKILLS_HEADER}"
            f"{skill_block}\n\n"
            "===\n\n"
            f"{agent_prompt_content}"
        )

    def estimate_prompt_tokens(self, agent_prompt_name: str) -> int:
        """
        Rough token count for the assembled system prompt.
        Uses the 4 chars/token heuristic — good enough for capacity planning.
        """
        from backend.prompts import load_prompt as _load
        try:
            agent_prompt = _load(agent_prompt_name)
        except FileNotFoundError:
            agent_prompt = ""
        return len(self._build_system_prompt(agent_prompt)) // 4

    # ── abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def run(self, input_data: InputT, db: Optional[AsyncSession] = None) -> OutputT:
        """Core agent logic. Implement in every subclass."""
        ...

    def validate(self, input_data: InputT) -> None:
        """
        Pre-run validation. Raise ValueError with a human-readable message.
        Default implementation does nothing.
        """

    # ── public entry point ────────────────────────────────────────────────────

    async def __call__(
        self,
        input_data: InputT,
        db:         Optional[AsyncSession] = None,
    ) -> OutputT:
        self.validate(input_data)

        log_id  = str(uuid.uuid4())
        started = time.monotonic()
        self._log.info("agent_start", log_id=log_id, skills=self.required_skills)

        try:
            output      = await self.run(input_data, db)
            duration_ms = int((time.monotonic() - started) * 1000)

            await self._persist_log(
                db=db, log_id=log_id,
                task=type(input_data).__name__,
                input_data=input_data, output_data=output,
                status=AgentLogStatus.success, duration_ms=duration_ms,
            )
            self._log.info("agent_success", log_id=log_id, duration_ms=duration_ms)
            return output

        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await self._persist_log(
                db=db, log_id=log_id,
                task=type(input_data).__name__,
                input_data=input_data, output_data=None,
                status=AgentLogStatus.failed, duration_ms=duration_ms,
                error=str(exc),
            )
            self._log.exception("agent_failed", log_id=log_id, error=str(exc))
            raise

    # ── internal ──────────────────────────────────────────────────────────────

    async def _persist_log(
        self,
        db:          Optional[AsyncSession],
        log_id:      str,
        task:        str,
        input_data:  InputT,
        output_data: Optional[OutputT],
        status:      AgentLogStatus,
        duration_ms: int,
        error:       Optional[str] = None,
    ) -> None:
        input_json                  = input_data.model_dump(mode="json")
        input_json["skills_loaded"] = list(self.required_skills)  # audit trail

        output_json: dict | None
        if output_data is not None:
            output_json = output_data.model_dump(mode="json")
        elif error:
            output_json = {"error": error}
        else:
            output_json = None

        if db is not None:
            entry = AgentLog(
                id=uuid.UUID(log_id),
                agent_name=self.agent_name,
                task=task,
                input_json=input_json,
                output_json=output_json,
                status=status,
                duration_ms=duration_ms,
            )
            db.add(entry)
            try:
                await db.flush()
            except Exception:
                self._log.warning("log_db_flush_failed", log_id=log_id)
        else:
            self._log.info(
                "agent_log_no_db",
                log_id=log_id,
                status=status.value,
                duration_ms=duration_ms,
            )
