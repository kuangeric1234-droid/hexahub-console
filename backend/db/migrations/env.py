"""
Alembic environment configuration.

Runs synchronously using psycopg2, even though the FastAPI app uses asyncpg.
The DATABASE_URL from config is rewritten at runtime:
  postgresql+asyncpg://... → postgresql+psycopg2://...
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── path: make `backend.*` importable when run from backend/ ──────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from backend.config import settings
from backend.db.models import Base  # noqa: F401 — registers all models

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_url() -> str:
    """Return a psycopg2-compatible URL for Alembic's sync runner."""
    return settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )


def run_migrations_offline() -> None:
    context.configure(
        url=get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_sync_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
