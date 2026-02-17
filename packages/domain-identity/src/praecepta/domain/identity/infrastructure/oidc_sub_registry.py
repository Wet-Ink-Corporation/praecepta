"""OIDC sub reservation for user uniqueness enforcement.

Uses the event store's PostgreSQL connection (via the eventsourcing
library's datastore) to manage a dedicated reservation table with a
unique constraint on the oidc_sub column.

Three-operation lifecycle:
1. reserve(oidc_sub, tenant_id)  -- Insert row; unique constraint prevents duplicates
2. confirm(oidc_sub, user_id) -- Update row with confirmed aggregate UUID
3. release(oidc_sub) -- Delete row (compensating action on failure)

Additional operation:
4. lookup(oidc_sub) -- Fast-path check for existing confirmed user
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from praecepta.foundation.domain.exceptions import ConflictError

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.application import Application

logger = logging.getLogger(__name__)

# SQL statements for OIDC sub registry operations
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_oidc_sub_registry (
    oidc_sub VARCHAR(255) PRIMARY KEY,
    user_id UUID,
    tenant_id VARCHAR(63) NOT NULL,
    reserved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    confirmed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_oidc_sub_registry_unconfirmed
    ON user_oidc_sub_registry (reserved_at)
    WHERE confirmed = FALSE;
"""

_RESERVE_SQL = """
INSERT INTO user_oidc_sub_registry (oidc_sub, tenant_id, confirmed)
VALUES (%s, %s, FALSE)
"""

_CONFIRM_SQL = """
UPDATE user_oidc_sub_registry
SET user_id = %s, confirmed = TRUE
WHERE oidc_sub = %s
"""

_RELEASE_SQL = """
DELETE FROM user_oidc_sub_registry
WHERE oidc_sub = %s AND confirmed = FALSE
"""

_LOOKUP_SQL = """
SELECT user_id FROM user_oidc_sub_registry
WHERE oidc_sub = %s AND confirmed = TRUE
"""


class OidcSubRegistry:
    """Manages OIDC sub reservations using the event store database.

    The registry shares the same PostgreSQL connection as the event store
    (accessed via the application's factory datastore). This avoids
    requiring a separate database connection pool.

    Attributes:
        _app: The UserApplication (provides access to datastore).
    """

    def __init__(self, app: Application[UUID]) -> None:
        self._app = app

    @classmethod
    def ensure_table_exists(cls, app: Application[UUID]) -> None:
        """Create the OIDC sub registry table if it does not exist.

        Called during application startup in the lifespan function.
        Uses CREATE TABLE IF NOT EXISTS for idempotency.

        No-op when using in-memory (POPO) persistence -- the table
        is only needed for PostgreSQL.

        Args:
            app: UserApplication with access to datastore.
        """
        if not hasattr(app.factory, "datastore"):
            logger.info("oidc_sub_registry_table_skipped: no postgres datastore available")
            return
        datastore = app.factory.datastore
        with datastore.transaction(commit=True) as cursor:
            cursor.execute(_CREATE_TABLE_SQL)
        logger.info("oidc_sub_registry_table_ensured")

    def reserve(self, oidc_sub: str, tenant_id: str) -> None:
        """Reserve an OIDC sub. Raises ConflictError if already taken.

        Args:
            oidc_sub: OIDC subject identifier to reserve.
            tenant_id: Tenant slug (for tracking).

        Raises:
            ConflictError: If the oidc_sub is already reserved or confirmed.
        """
        from eventsourcing.persistence import IntegrityError
        from psycopg.errors import UniqueViolation

        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        try:
            with datastore.transaction(commit=True) as cursor:
                cursor.execute(_RESERVE_SQL, (oidc_sub, tenant_id))
        except (UniqueViolation, IntegrityError) as err:
            raise ConflictError(
                f"OIDC sub '{oidc_sub}' is already provisioned",
                oidc_sub=oidc_sub,
            ) from err

    def confirm(self, oidc_sub: str, user_id: UUID) -> None:
        """Confirm reservation with the user aggregate UUID.

        Args:
            oidc_sub: Previously reserved OIDC sub.
            user_id: UUID of the created User aggregate.
        """
        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        with datastore.transaction(commit=True) as cursor:
            cursor.execute(_CONFIRM_SQL, (str(user_id), oidc_sub))

    def release(self, oidc_sub: str) -> None:
        """Release an unconfirmed reservation (compensating action).

        Deletes the reservation row only if not yet confirmed.
        Idempotent (no error if row does not exist).

        Args:
            oidc_sub: OIDC sub to release.
        """
        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        with datastore.transaction(commit=True) as cursor:
            cursor.execute(_RELEASE_SQL, (oidc_sub,))

    def lookup(self, oidc_sub: str) -> UUID | None:
        """Look up confirmed user_id for an OIDC sub (fast-path check).

        Returns the user_id if a confirmed reservation exists, otherwise None.

        Args:
            oidc_sub: OIDC subject identifier to look up.

        Returns:
            UUID of the confirmed User aggregate, or None if not found.
        """
        datastore = self._app.factory.datastore  # type: ignore[attr-defined]
        with datastore.transaction(commit=False) as cursor:
            cursor.execute(_LOOKUP_SQL, (oidc_sub,))
            row = cursor.fetchone()
            if row is None:
                return None
            user_id: UUID = row["user_id"]
            return user_id
