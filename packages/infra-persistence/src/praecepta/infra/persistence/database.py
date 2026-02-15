"""Centralized database session factories for application endpoints.

Provides both async and sync database session management:
- Async: For query endpoints using async DB reads (DbSession)
- Sync: For projections and other sync-context code

Usage:
    # Async (query endpoints)
    from praecepta.infra.persistence.database import DbSession

    @router.get("/items")
    async def list_items(session: DbSession) -> list[Item]:
        ...

    # Sync (projections)
    from praecepta.infra.persistence.database import get_sync_session_factory
    session_factory = get_sync_session_factory()
    with session_factory() as session:
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class DatabaseSettings(BaseSettings):
    """Database connection configuration from environment variables.

    Loads configuration from environment variables with ``DATABASE_`` prefix:
    - DATABASE_HOST: PostgreSQL host (default: localhost)
    - DATABASE_PORT: PostgreSQL port (default: 5432)
    - DATABASE_USER: PostgreSQL user (default: postgres)
    - DATABASE_PASSWORD: PostgreSQL password (default: postgres)
    - DATABASE_NAME: PostgreSQL database name (default: app)

    Example:
        >>> settings = DatabaseSettings()
        >>> settings.database_url
        'postgresql+psycopg://postgres:postgres@localhost:5432/app'
    """

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    user: str = Field(default="postgres", description="PostgreSQL user")
    password: str = Field(default="postgres", repr=False, description="PostgreSQL password")
    name: str = Field(default="app", description="PostgreSQL database name")

    @property
    def database_url(self) -> str:
        """Build the async database connection URL.

        Returns:
            PostgreSQL async connection string using psycopg driver.
        """
        return (
            f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        )


# Module-level async engine singleton (created on first use)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# Module-level sync engine singleton for projections
_sync_engine: Engine | None = None
_sync_session_factory: sessionmaker[Session] | None = None


def _get_database_url() -> str:
    """Build database URL from DatabaseSettings.

    Returns:
        PostgreSQL async connection string.
    """
    settings = DatabaseSettings()
    return settings.database_url


def get_engine() -> AsyncEngine:
    """Get or create the async database engine singleton.

    The engine is created once per process and reused for all requests.
    Uses connection pooling with sensible defaults for production.

    Returns:
        AsyncEngine configured for the application database.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            _get_database_url(),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory singleton.

    Returns:
        Async session factory configured with proper settings.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Dependency that provides an async database session.

    Creates a new session for each request using the shared session factory.
    Session is automatically closed after the request completes.

    Yields:
        AsyncSession for database operations.

    Example:
        @router.get("/blocks/{block_id}")
        async def get_block(
            block_id: UUID,
            session: Annotated[AsyncSession, Depends(get_db_session)],
        ) -> BlockResponse:
            result = await session.execute(...)
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Type alias for cleaner endpoint signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_sync_engine() -> Engine:
    """Get or create the sync database engine singleton.

    Used by projections that run in sync context.
    Shares the same database URL as the async engine.

    Returns:
        Engine configured for the application database.
    """
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            _get_database_url(),
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    """Get or create the sync session factory singleton.

    Used by projections for direct sync database access.

    Returns:
        Sync session factory configured with proper settings.
    """
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            get_sync_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sync_session_factory


async def dispose_engine() -> None:
    """Dispose of all database engines and connection pools.

    Call this during application shutdown to clean up resources.
    Handles both async and sync engines.
    """
    global _engine, _session_factory, _sync_engine, _sync_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
        _sync_session_factory = None
