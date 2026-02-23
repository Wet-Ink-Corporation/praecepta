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

    # DatabaseManager (advanced, e.g. multiple databases)
    from praecepta.infra.persistence.database import DatabaseManager
    manager = DatabaseManager(settings)
    engine = manager.get_engine()
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from pydantic import Field, model_validator
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

    # Async engine pool settings
    async_pool_size: int = Field(
        default=10, ge=1, le=100, description="Async engine base pool size"
    )
    async_max_overflow: int = Field(
        default=5, ge=0, le=100, description="Async engine max overflow connections"
    )

    # Sync engine pool settings (for projections)
    sync_pool_size: int = Field(default=3, ge=1, le=50, description="Sync engine base pool size")
    sync_max_overflow: int = Field(
        default=2, ge=0, le=50, description="Sync engine max overflow connections"
    )

    # Shared pool settings
    pool_timeout: int = Field(
        default=30, ge=1, le=300, description="Seconds to wait for a connection from pool"
    )
    pool_recycle: int = Field(
        default=3600, ge=60, le=86400, description="Seconds before a connection is recycled"
    )
    echo: bool = Field(default=False, description="Echo SQL statements to log")

    @model_validator(mode="after")
    def _validate_connection_url(self) -> DatabaseSettings:
        """Validate the built connection URL is parseable by SQLAlchemy."""
        from sqlalchemy.engine.url import make_url

        try:
            make_url(self.database_url)
        except Exception as exc:
            msg = f"Invalid database connection URL: {exc}"
            raise ValueError(msg) from exc
        return self

    @property
    def database_url(self) -> str:
        """Build the async database connection URL.

        Returns:
            PostgreSQL async connection string using psycopg driver.
        """
        return (
            f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        )


class DatabaseManager:
    """Encapsulates database engine and session factory lifecycle.

    Manages both async and sync engines with their session factories,
    providing clean creation and disposal semantics. Multiple instances
    can coexist with different configurations (e.g. for testing).

    Usage:
        manager = DatabaseManager(DatabaseSettings())
        engine = manager.get_engine()
        await manager.dispose()
    """

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._sync_engine: Engine | None = None
        self._sync_session_factory: sessionmaker[Session] | None = None

    @property
    def settings(self) -> DatabaseSettings:
        """The settings used by this manager."""
        return self._settings

    def get_engine(self) -> AsyncEngine:
        """Get or create the async database engine.

        Returns:
            AsyncEngine configured from this manager's settings.
        """
        if self._engine is None:
            s = self._settings
            self._engine = create_async_engine(
                s.database_url,
                pool_size=s.async_pool_size,
                max_overflow=s.async_max_overflow,
                pool_pre_ping=True,
                pool_timeout=s.pool_timeout,
                pool_recycle=s.pool_recycle,
                echo=s.echo,
            )
        return self._engine

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create the async session factory.

        Returns:
            Async session factory bound to this manager's engine.
        """
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
        return self._session_factory

    def get_sync_engine(self) -> Engine:
        """Get or create the sync database engine.

        Returns:
            Sync Engine configured from this manager's settings.
        """
        if self._sync_engine is None:
            s = self._settings
            self._sync_engine = create_engine(
                s.database_url,
                pool_size=s.sync_pool_size,
                max_overflow=s.sync_max_overflow,
                pool_pre_ping=True,
                pool_timeout=s.pool_timeout,
                pool_recycle=s.pool_recycle,
                echo=s.echo,
            )
        return self._sync_engine

    def get_sync_session_factory(self) -> sessionmaker[Session]:
        """Get or create the sync session factory.

        Returns:
            Sync session factory bound to this manager's sync engine.
        """
        if self._sync_session_factory is None:
            self._sync_session_factory = sessionmaker(
                self.get_sync_engine(),
                expire_on_commit=False,
                autoflush=False,
            )
        return self._sync_session_factory

    async def get_db_session(self) -> AsyncIterator[AsyncSession]:
        """Async generator yielding a database session.

        Yields:
            AsyncSession for database operations.
        """
        factory = self.get_session_factory()
        async with factory() as session:
            try:
                yield session
            finally:
                await session.close()

    async def dispose(self) -> None:
        """Dispose of all engines and connection pools.

        Safe to call multiple times.
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
            self._sync_session_factory = None


# ---------------------------------------------------------------------------
# Default singleton manager (backward-compatible module-level API)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_database_manager() -> DatabaseManager:
    """Get the default DatabaseManager singleton.

    Returns:
        DatabaseManager configured from environment variables.
    """
    return DatabaseManager(DatabaseSettings())


def _get_database_url() -> str:
    """Build database URL from DatabaseSettings.

    Returns:
        PostgreSQL async connection string.
    """
    return get_database_manager().settings.database_url


def get_engine() -> AsyncEngine:
    """Get the default async database engine singleton.

    Delegates to the default DatabaseManager.
    """
    return get_database_manager().get_engine()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the default async session factory singleton.

    Delegates to the default DatabaseManager.
    """
    return get_database_manager().get_session_factory()


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
    """Get the default sync database engine singleton.

    Delegates to the default DatabaseManager.
    """
    return get_database_manager().get_sync_engine()


def get_sync_session_factory() -> sessionmaker[Session]:
    """Get the default sync session factory singleton.

    Delegates to the default DatabaseManager.
    """
    return get_database_manager().get_sync_session_factory()


async def dispose_engine() -> None:
    """Dispose of all database engines and connection pools.

    Delegates to the default DatabaseManager.
    """
    await get_database_manager().dispose()
