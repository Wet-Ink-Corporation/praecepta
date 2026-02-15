"""SQLAlchemy session event handler for tenant context propagation.

Bridges the request-scoped ContextVar (set by middleware) to a PostgreSQL
session variable (consumed by RLS policies). Uses SET LOCAL for
transaction-scoped safety in connection-pooled environments.

Registration: Called once during application lifespan startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from praecepta.foundation.application.context import (
    NoRequestContextError,
    get_current_tenant_id,
)

logger = logging.getLogger(__name__)


def _set_tenant_context_on_begin(
    session: Session,
    transaction: object,
    connection: object,
) -> None:
    """Set app.current_tenant as PostgreSQL session variable.

    Fires after Session.begin() (including savepoints). Reads tenant_id
    from the ContextVar populated by request middleware and executes
    SET LOCAL on the raw connection.

    SET LOCAL is transaction-scoped: automatically cleared on COMMIT
    or ROLLBACK. Safe for connection pooling.

    Args:
        session: The SQLAlchemy Session.
        transaction: The SessionTransaction (unused).
        connection: The Connection object to execute SET LOCAL on.
    """
    try:
        tenant_id = get_current_tenant_id()
    except NoRequestContextError:
        # No request context: migrations, health checks, admin tools,
        # background tasks. RLS default-deny returns zero rows.
        logger.debug("tenant_context_skipped: no_request_context")
        return

    if not tenant_id:
        logger.warning("tenant_context_empty: tenant_id is empty string")
        return

    # Use set_config() with is_local=true for transaction-scoped context.
    # set_config() accepts parameterized values (unlike SET LOCAL which
    # rejects prepared statement parameters). The third argument 'true'
    # makes it equivalent to SET LOCAL -- cleared on commit/rollback.
    connection.execute(  # type: ignore[attr-defined]
        text("SELECT set_config('app.current_tenant', :tenant, true)"),
        {"tenant": str(tenant_id)},
    )
    logger.debug("tenant_context_set: tenant_id=%s", tenant_id)


def register_tenant_context_handler() -> None:
    """Register the after_begin event handler on the Session class.

    Must be called once during application startup (lifespan).
    Applies to ALL sessions created from any engine -- both async
    and sync sessions fire after_begin through the same Session class.

    Idempotent: SQLAlchemy deduplicates identical listener registrations.
    """
    event.listen(Session, "after_begin", _set_tenant_context_on_begin)
    logger.info("tenant_context_handler_registered")
