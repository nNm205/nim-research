"""Database engine + session factories.

Pool tuning notes:

- ``pool_size=20`` / ``max_overflow=20``: Supabase free tier allows 60
  connections; we leave headroom for migrations / external tools.
- ``pool_recycle=300``: drop connections older than 5 minutes. Supabase's
  pooler drops idle backends after a few minutes; without recycle we'd
  hit ``OperationalError`` on the next checkout.

Compatibility with Supabase / Supavisor / PgBouncer in transaction mode:

- ``pool_pre_ping`` is **disabled for the async engine**. The ping calls
  ``await conn.fetchrow(';')`` which goes through asyncpg's prepared-
  statement protocol; the pooler may have swapped to a different backend
  by the time the ping runs and the prepared statement no longer exists.
  We rely on ``pool_recycle`` instead — connections older than 5 minutes
  are dropped and reopened.
- ``connect_args.statement_cache_size = 0`` and
  ``prepared_statement_cache_size = 0`` (SQLAlchemy ↔ asyncpg alias)
  disable asyncpg's prepared-statement cache.
- ``prepared_statement_name_func`` returns a UUID-based name for every
  statement so any name a pooler-swapped backend has never seen is fine
  (asyncpg generates a fresh name each time).
- ``server_settings`` sets per-connection guardrails: 30 s statement
  timeout and 60 s idle-in-transaction timeout.

Sync engine kept for the legacy CRUD endpoints in projects/documents
that still use ``Session``. Sync psycopg2 doesn't need any of the
asyncpg-specific switches.
"""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.config import settings


# ── Pool tuning constants ────────────────────────────────────────────────────

_POOL_SIZE = 20
_MAX_OVERFLOW = 20
_POOL_RECYCLE_S = 300

_PG_STATEMENT_TIMEOUT_MS = "30000"          # 30 s per query
_PG_IDLE_IN_TX_TIMEOUT_MS = "60000"          # 60 s idle in transaction


# ── URL helpers ──────────────────────────────────────────────────────────────


def _to_sync_url(url: str) -> str:
    """Force the URL to use the sync psycopg2 driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _to_async_url(url: str) -> str:
    """Force the URL to use the async asyncpg driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _unique_stmt_name() -> str:
    """asyncpg statement name generator — unique per call.

    Default asyncpg generates ``__asyncpg_stmt_<sequence>__`` which is
    only valid on the originating physical connection. With Supavisor /
    PgBouncer transaction mode we may be reassigned to a different
    backend between calls; using a UUID-based name avoids name
    collisions there.
    """
    return f"__asyncpg_{uuid.uuid4().hex}__"


# ── Sync engine ──────────────────────────────────────────────────────────────
sync_database_url = _to_sync_url(settings.DATABASE_URL)

engine = create_engine(
    sync_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_recycle=_POOL_RECYCLE_S,
    connect_args={
        # psycopg2 takes server-level GUCs via ``options``.
        "options": (
            f"-c statement_timeout={_PG_STATEMENT_TIMEOUT_MS} "
            f"-c idle_in_transaction_session_timeout={_PG_IDLE_IN_TX_TIMEOUT_MS}"
        ),
    },
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Async engine ─────────────────────────────────────────────────────────────
async_database_url = _to_async_url(settings.DATABASE_URL)

async_engine = create_async_engine(
    async_database_url,
    echo=settings.DEBUG,
    # IMPORTANT: must be False with Supabase / Supavisor / PgBouncer
    # (transaction mode). The async ping uses asyncpg's prepared statement
    # protocol and breaks when the pooler reassigns backends.
    pool_pre_ping=False,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_recycle=_POOL_RECYCLE_S,
    connect_args={
        # Disable asyncpg's prepared-statement cache. ``statement_cache_size``
        # is the native asyncpg name; ``prepared_statement_cache_size`` is
        # the SQLAlchemy alias. Set both for safety across versions.
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        # Generate a fresh statement name per call so a pooler-swapped
        # backend can never see a name another backend already used.
        "prepared_statement_name_func": _unique_stmt_name,
        # GUCs we want set on every connection.
        "server_settings": {
            "statement_timeout": _PG_STATEMENT_TIMEOUT_MS,
            "idle_in_transaction_session_timeout": _PG_IDLE_IN_TX_TIMEOUT_MS,
        },
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session
