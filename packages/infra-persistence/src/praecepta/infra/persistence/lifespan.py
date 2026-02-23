"""Persistence lifespan hook for startup/shutdown resource management.

Handles:
- Tenant context handler registration (RLS activation)
- Database health check on startup (SELECT 1)
- Engine disposal on shutdown
- Redis client close on shutdown

Priority 75 ensures persistence starts AFTER observability (50)
but BEFORE the event store (100) and projections (200).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from praecepta.foundation.application import LifespanContribution
from praecepta.infra.persistence.database import get_database_manager
from praecepta.infra.persistence.redis_client import get_redis_factory
from praecepta.infra.persistence.tenant_context import register_tenant_context_handler

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _persistence_lifespan(app: Any) -> AsyncIterator[None]:
    """Manage persistence resources across the application lifecycle.

    Startup:
        1. Register tenant context handler for RLS.
        2. Execute ``SELECT 1`` health check on async engine.

    Shutdown:
        1. Dispose database engines and connection pools.
        2. Close Redis client connections.

    Args:
        app: The application instance (unused but required by protocol).
    """
    manager = get_database_manager()

    # 1. Register tenant context handler
    register_tenant_context_handler()
    logger.info("persistence_lifespan: tenant context handler registered")

    # 2. Database health check
    engine = manager.get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("persistence_lifespan: database health check passed")

    # 3. Connection budget warning (CF-04)
    settings = manager.settings
    total_budget = (
        settings.async_pool_size
        + settings.async_max_overflow
        + settings.sync_pool_size
        + settings.sync_max_overflow
    )
    if total_budget > 80:
        logger.warning(
            "persistence_lifespan: total connection budget %d exceeds 80 "
            "(80%% of default max_connections=100). Consider tuning pool sizes.",
            total_budget,
        )
    else:
        logger.info("persistence_lifespan: total connection budget %d", total_budget)

    try:
        yield
    finally:
        # Shutdown: dispose engines
        await manager.dispose()
        logger.info("persistence_lifespan: database engines disposed")

        # Shutdown: close Redis
        try:
            redis_factory = get_redis_factory()
            await redis_factory.close()
            logger.info("persistence_lifespan: redis client closed")
        except Exception:
            logger.warning("persistence_lifespan: failed to close redis client", exc_info=True)


lifespan_contribution = LifespanContribution(
    hook=_persistence_lifespan,
    priority=75,
)
