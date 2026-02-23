"""Reusable async Alembic ``env.py`` template for Praecepta applications.

This module provides a ``run_async_migrations()`` coroutine that can be
imported into a project's Alembic ``env.py`` to support async migrations
with SQLAlchemy 2.x and PostgreSQL.

Usage in your project's ``env.py``::

    from praecepta.infra.persistence.alembic_env_template import (
        run_async_migrations,
    )
    from praecepta.infra.persistence.database import get_database_manager

    # Import your declarative base
    from myapp.models import Base

    manager = get_database_manager()
    engine = manager.get_engine()

    import asyncio
    asyncio.run(run_async_migrations(engine, Base.metadata))

Note:
    For offline (SQL-only) migrations, use Alembic's built-in
    ``context.configure(url=..., literal_binds=True)`` pattern instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import context

if TYPE_CHECKING:
    from sqlalchemy import MetaData
    from sqlalchemy.ext.asyncio import AsyncEngine


def _do_run_migrations(connection: object, target_metadata: MetaData) -> None:
    """Run migrations within a synchronous connection context.

    Args:
        connection: SQLAlchemy synchronous connection (from ``run_sync``).
        target_metadata: Declarative metadata for autogenerate support.
    """
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations(
    engine: AsyncEngine,
    target_metadata: MetaData,
) -> None:
    """Execute Alembic migrations asynchronously.

    Connects to the database using the provided async engine,
    then delegates to ``_do_run_migrations`` via ``run_sync``.

    Args:
        engine: SQLAlchemy ``AsyncEngine`` to use for migrations.
        target_metadata: Declarative metadata for autogenerate support.

    Example::

        import asyncio
        from praecepta.infra.persistence.alembic_env_template import (
            run_async_migrations,
        )
        from praecepta.infra.persistence.database import get_database_manager
        from myapp.models import Base

        manager = get_database_manager()
        asyncio.run(run_async_migrations(manager.get_engine(), Base.metadata))
    """
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations, target_metadata)
    await engine.dispose()
