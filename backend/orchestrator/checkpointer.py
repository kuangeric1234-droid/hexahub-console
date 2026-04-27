"""
Checkpointer factory for the LangGraph workflow.

Development / testing
---------------------
    checkpointer = get_memory_checkpointer()

Production (Postgres)
---------------------
    checkpointer = await get_postgres_checkpointer(settings.DATABASE_URL)

The Postgres checkpointer requires the langgraph-checkpoint-postgres package
and creates its own tables (langgraph_checkpoints, langgraph_writes, etc.)
on first use.  It uses a *sync* psycopg connection string, not asyncpg.
"""
from __future__ import annotations

import warnings

import structlog
from langgraph.checkpoint.memory import MemorySaver

log = structlog.get_logger()


def get_memory_checkpointer() -> MemorySaver:
    """In-memory checkpointer — state is lost on process restart."""
    return MemorySaver()


async def get_postgres_checkpointer(async_database_url: str):
    """
    Persistent Postgres checkpointer for production.

    Parameters
    ----------
    async_database_url
        The asyncpg DATABASE_URL (postgresql+asyncpg://...).
        This function converts it to the psycopg format required by
        langgraph-checkpoint-postgres.

    Returns
    -------
    AsyncPostgresSaver | MemorySaver
        AsyncPostgresSaver if the package is available, MemorySaver otherwise.
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # AsyncPostgresSaver expects a plain postgresql:// or psycopg:// URL
        sync_url = (
            async_database_url
            .replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgresql+psycopg2://", "postgresql://")
        )

        checkpointer = AsyncPostgresSaver.from_conn_string(sync_url)
        await checkpointer.setup()  # creates checkpoint tables if absent
        log.info("postgres_checkpointer_ready")
        return checkpointer

    except ImportError:
        warnings.warn(
            "langgraph-checkpoint-postgres is not installed. "
            "Falling back to MemorySaver (state will not survive restarts). "
            "Install with: pip install langgraph-checkpoint-postgres",
            RuntimeWarning,
            stacklevel=2,
        )
        return MemorySaver()
