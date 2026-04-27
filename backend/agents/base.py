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
from typing import Generic, Optional, TypeVar

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import AgentLog, AgentLogStatus
from backend.llm.client import LLMClient, LLMProvider

log = structlog.get_logger()

InputT  = TypeVar("InputT",  bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    # ── class-level config (override in subclasses) ───────────────────────────
    agent_name:       str            # required — set on every subclass
    default_provider: LLMProvider  = LLMProvider.ANTHROPIC
    default_model:    Optional[str] = None

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm  = llm_client or LLMClient(
            provider=self.default_provider,
            model=self.default_model,
        )
        self._log = log.bind(agent=self.agent_name)

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
        self._log.info("agent_start", log_id=log_id)

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
        input_json  = input_data.model_dump(mode="json")
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
