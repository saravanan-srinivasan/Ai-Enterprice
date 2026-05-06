"""
utils/database.py
-----------------
Async PostgreSQL connection management with SQLAlchemy.
Provides session factory, lifespan management, and migration helpers.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

from utils.config import settings
from utils.logger import get_logger
from utils.models import Base

logger = get_logger(__name__, service="database")

# ─── Engine Configuration ────────────────────────────────────────────────────

def _create_engine() -> AsyncEngine:
    """
    Create an async SQLAlchemy engine with production-grade pool settings.
    Uses NullPool for testing environments to avoid connection reuse issues.
    """
    pool_class = NullPool if settings.app_env == "testing" else AsyncAdaptedQueuePool

    engine_kwargs = {
        "echo": settings.debug,
        "future": True,
    }

    if pool_class != NullPool:
        engine_kwargs.update(
            {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_pre_ping": True,
                "pool_recycle": 3600,
                "pool_timeout": 30,
            }
        )
    else:
        engine_kwargs["poolclass"] = NullPool

    return create_async_engine(settings.database_url, **engine_kwargs)


# Module-level singletons
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


# ─── Session Dependency ──────────────────────────────────────────────────────

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a transactional database session.
    Automatically commits on success and rolls back on exception.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def db_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager version for use outside FastAPI dependency injection.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ─── Schema Management ───────────────────────────────────────────────────────

async def create_all_tables() -> None:
    """Create all ORM-mapped tables. Idempotent — safe to call on startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_schema_ready", tables=list(Base.metadata.tables.keys()))


async def drop_all_tables() -> None:
    """Drop all tables. DANGEROUS — for testing only."""
    if settings.app_env == "production":
        raise RuntimeError("drop_all_tables is not permitted in production")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("database_schema_dropped")


async def dispose_engine() -> None:
    """Gracefully close all pooled connections."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("database_engine_disposed")
