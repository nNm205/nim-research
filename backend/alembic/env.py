"""Alembic env that supports both sync and async SQLAlchemy URLs.

The application uses `postgresql+asyncpg://...` for runtime, but Alembic's
default offline/online migration model is sync. We detect an async driver
in the URL and switch to AsyncEngine + connection.run_sync to keep both
worlds happy.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.database.base import Base
from app.config import settings
import app.models  # noqa: F401  — populate metadata


# ── Alembic config wiring ────────────────────────────────────────────────────

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_async_url(url: str) -> bool:
    return "+asyncpg" in url or "+aiosqlite" in url or "+aiomysql" in url


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


# ── Modes ────────────────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Generate SQL only, no DB connection needed."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    """Online migrations using an async engine (asyncpg driver)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online_sync() -> None:
    """Online migrations using a sync engine (psycopg2/psycopg driver)."""
    from sqlalchemy import engine_from_config

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _do_run_migrations(connection)


# ── Entry point ──────────────────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
elif _is_async_url(config.get_main_option("sqlalchemy.url") or ""):
    asyncio.run(run_migrations_online_async())
else:
    run_migrations_online_sync()
