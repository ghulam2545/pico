"""
Provides asynchronous Postgres engine and session management.
"""
from config.settings import settings
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
import structlog

log = structlog.get_logger()

db_url = make_url(settings.postgres_url)

log.info(
    "database_engine_initialized",
    database=db_url.database,
    host=db_url.host,
    port=db_url.port,
    username=db_url.username
)

_engine = create_async_engine(
    settings.postgres_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

_AsyncSessionLocal = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager that yields an AsyncSession and handles commit/rollback."""
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_engine():
    return _engine
