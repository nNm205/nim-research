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

_POOL_SIZE = 20
_MAX_OVERFLOW = 20
_POOL_RECYCLE_S = 300

_PG_STATEMENT_TIMEOUT_MS = "120000"         
_PG_IDLE_IN_TX_TIMEOUT_MS = "1800000"        

def _to_sync_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _to_async_url(url: str) -> str:
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
    return f"__asyncpg_{uuid.uuid4().hex}__"


def _is_pooler_url(url: str) -> bool:
    lowered = (url or "").lower()
    if "pooler.supabase.com" in lowered:
        return True
    if "pgbouncer" in lowered:
        return True
    if ":6543/" in lowered or ":6543?" in lowered or lowered.endswith(":6543"):
        return True
    return False


_USING_POOLER = _is_pooler_url(settings.DATABASE_URL)
sync_database_url = _to_sync_url(settings.DATABASE_URL)

engine = create_engine(
    sync_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_recycle=_POOL_RECYCLE_S,
    connect_args={
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

async_database_url = _to_async_url(settings.DATABASE_URL)

_async_connect_args: dict = {
    "server_settings": {
        "statement_timeout": _PG_STATEMENT_TIMEOUT_MS,
        "idle_in_transaction_session_timeout": _PG_IDLE_IN_TX_TIMEOUT_MS,
    },
}
if _USING_POOLER:
    _async_connect_args.update(
        statement_cache_size=0,
        prepared_statement_cache_size=0,
        prepared_statement_name_func=_unique_stmt_name,
    )

async_engine = create_async_engine(
    async_database_url,
    echo=settings.DEBUG,
    pool_pre_ping=not _USING_POOLER,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_recycle=_POOL_RECYCLE_S,
    connect_args=_async_connect_args,
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
