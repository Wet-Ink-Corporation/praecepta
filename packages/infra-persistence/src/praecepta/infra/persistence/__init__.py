"""Praecepta Infra Persistence — session factories, RLS helpers, tenant context."""

from praecepta.infra.persistence.database import (
    DatabaseManager,
    DatabaseSettings,
    DbSession,
    dispose_engine,
    get_database_manager,
    get_db_session,
    get_engine,
    get_session_factory,
    get_sync_engine,
    get_sync_session_factory,
)
from praecepta.infra.persistence.lifespan import lifespan_contribution
from praecepta.infra.persistence.redis_client import RedisFactory, get_redis_factory
from praecepta.infra.persistence.redis_settings import RedisSettings
from praecepta.infra.persistence.rls_helpers import (
    create_tenant_isolation_policy,
    disable_rls,
    drop_tenant_isolation_policy,
    enable_rls,
)
from praecepta.infra.persistence.tenant_context import register_tenant_context_handler

__all__ = [
    "DatabaseManager",
    "DatabaseSettings",
    "DbSession",
    "RedisFactory",
    "RedisSettings",
    "create_tenant_isolation_policy",
    "disable_rls",
    "dispose_engine",
    "drop_tenant_isolation_policy",
    "enable_rls",
    "get_database_manager",
    "get_db_session",
    "get_engine",
    "get_redis_factory",
    "get_session_factory",
    "get_sync_engine",
    "get_sync_session_factory",
    "lifespan_contribution",
    "register_tenant_context_handler",
]
