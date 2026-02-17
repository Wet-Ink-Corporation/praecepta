"""Slug reservation for tenant uniqueness enforcement.

Uses the event store's PostgreSQL connection (via the eventsourcing
library's datastore) to manage a dedicated reservation table with a
unique constraint on the slug column.

Three-operation lifecycle:
1. reserve(slug)  -- Insert row; unique constraint prevents duplicates
2. confirm(slug, tenant_id) -- Update row with confirmed aggregate UUID
3. release(slug) -- Delete row (compensating action on failure)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from praecepta.foundation.domain.exceptions import ConflictError

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.application import Application

logger = logging.getLogger(__name__)

# SQL statements for slug registry operations
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tenant_slug_registry (
    slug VARCHAR(63) PRIMARY KEY,
    tenant_id UUID,
    reserved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    confirmed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_slug_registry_unconfirmed
    ON tenant_slug_registry (reserved_at)
    WHERE confirmed = FALSE;
"""

_RESERVE_SQL = "INSERT INTO tenant_slug_registry (slug, confirmed) VALUES (%s, FALSE)"

_CONFIRM_SQL = "UPDATE tenant_slug_registry SET tenant_id = %s, confirmed = TRUE WHERE slug = %s"

_RELEASE_SQL = "DELETE FROM tenant_slug_registry WHERE slug = %s AND confirmed = FALSE"

_DECOMMISSION_SQL = "DELETE FROM tenant_slug_registry WHERE slug = %s"


class SlugRegistry:
    """Manages tenant slug reservations using the event store database.

    The registry shares the same PostgreSQL connection as the event store
    (accessed via the application's factory datastore). This avoids
    requiring a separate database connection pool.

    Attributes:
        _app: The TenantApplication (provides access to datastore).
    """

    def __init__(self, app: Application[UUID]) -> None:
        self._app = app

    @classmethod
    def ensure_table_exists(cls, app: Application[UUID]) -> None:
        """Create the slug registry table if it does not exist.

        Called during application startup in the lifespan function.
        Uses CREATE TABLE IF NOT EXISTS for idempotency.

        No-op when using in-memory (POPO) persistence -- the table
        is only needed for PostgreSQL.

        Args:
            app: TenantApplication with access to datastore.
        """
        if not hasattr(app.factory, "datastore"):
            logger.info("slug_registry_table_skipped: no postgres datastore available")
            return
        datastore = app.factory.datastore
        with datastore.transaction(commit=True) as cursor:
            cursor.execute(_CREATE_TABLE_SQL)
        logger.info("slug_registry_table_ensured")

    def reserve(self, slug: str) -> None:
        """Reserve a slug. Raises ConflictError if already taken.

        Uses INSERT with the PRIMARY KEY constraint to atomically
        prevent duplicate slugs. psycopg raises UniqueViolation
        on conflict, which is caught and translated.

        Args:
            slug: Tenant slug to reserve.

        Raises:
            ConflictError: If the slug is already reserved or confirmed.
        """
        from psycopg.errors import UniqueViolation

        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        try:
            with datastore.transaction(commit=True) as cursor:
                cursor.execute(_RESERVE_SQL, (slug,))
        except UniqueViolation as err:
            raise ConflictError(
                f"Slug '{slug}' is already taken",
                slug=slug,
            ) from err

    def confirm(self, slug: str, tenant_id: UUID) -> None:
        """Confirm reservation with the tenant aggregate UUID.

        Updates the row to set tenant_id and confirmed=TRUE.

        Args:
            slug: Previously reserved slug.
            tenant_id: UUID of the created Tenant aggregate.
        """
        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        with datastore.transaction(commit=True) as cursor:
            cursor.execute(_CONFIRM_SQL, (str(tenant_id), slug))

    def release(self, slug: str) -> None:
        """Release an unconfirmed reservation (compensating action).

        Deletes the reservation row only if not yet confirmed.
        Called when aggregate creation fails after slug reservation.
        Idempotent (no error if row does not exist).

        Args:
            slug: Slug to release.
        """
        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        with datastore.transaction(commit=True) as cursor:
            cursor.execute(_RELEASE_SQL, (slug,))

    def decommission(self, slug: str) -> None:
        """Release a confirmed slug reservation on tenant decommission.

        Unlike release() which only deletes unconfirmed reservations,
        decommission() unconditionally removes the slug entry (confirmed
        or not). This makes the slug available for reuse after tenant
        decommissioning.

        Idempotent: no error if the slug does not exist.

        Args:
            slug: Tenant slug to permanently release.
        """
        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        with datastore.transaction(commit=True) as cursor:
            cursor.execute(_DECOMMISSION_SQL, (slug,))
