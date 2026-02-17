"""Projection repository for tenant_configuration table.

Sync repository (projections use sync pattern).
RLS-aware: queries filtered by app.current_tenant session variable
set by tenant_context after_begin handler.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


class ConfigRepository:
    """Read/write access to tenant_configuration projection.

    All methods are synchronous per projection pattern.
    Tenant isolation enforced by RLS on tenant_configuration table.

    Args:
        session_factory: Callable returning a SQLAlchemy Session context manager.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def get(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        """Read single config entry from projection.

        Args:
            tenant_id: Tenant slug identifier.
            key: Configuration key string.

        Returns:
            Config value dict (JSONB content) or None if not found.
        """
        with self._session_factory() as session:
            result = session.execute(
                text(
                    "SELECT config_value FROM tenant_configuration "
                    "WHERE tenant_id = :tenant_id AND config_key = :key"
                ),
                {"tenant_id": tenant_id, "key": key},
            )
            row = result.fetchone()
            return row[0] if row else None

    def get_all(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        """Read all config entries for a tenant.

        Args:
            tenant_id: Tenant slug identifier.

        Returns:
            Dict mapping config_key -> config_value dict.
        """
        with self._session_factory() as session:
            result = session.execute(
                text(
                    "SELECT config_key, config_value "
                    "FROM tenant_configuration "
                    "WHERE tenant_id = :tenant_id"
                ),
                {"tenant_id": tenant_id},
            )
            return {row[0]: row[1] for row in result.fetchall()}

    def upsert(
        self,
        tenant_id: str,
        key: str,
        value: dict[str, Any],
        updated_by: str,
    ) -> None:
        """Write config entry using PostgreSQL UPSERT (idempotent).

        Uses INSERT ... ON CONFLICT DO UPDATE for replay safety.

        Args:
            tenant_id: Tenant slug identifier.
            key: Configuration key string.
            value: Config value dict (JSONB content).
            updated_by: Operator user ID for audit.
        """
        with self._session_factory() as session:
            session.execute(
                text(
                    "INSERT INTO tenant_configuration "
                    "(tenant_id, config_key, config_value, updated_by, updated_at) "
                    "VALUES (:tenant_id, :key, :value, :updated_by, NOW()) "
                    "ON CONFLICT (tenant_id, config_key) DO UPDATE SET "
                    "config_value = EXCLUDED.config_value, "
                    "updated_by = EXCLUDED.updated_by, "
                    "updated_at = NOW()"
                ),
                {
                    "tenant_id": tenant_id,
                    "key": key,
                    "value": json.dumps(value),
                    "updated_by": updated_by,
                },
            )
            session.commit()

    def delete(self, tenant_id: str, key: str) -> bool:
        """Delete config entry.

        Args:
            tenant_id: Tenant slug identifier.
            key: Configuration key string.

        Returns:
            True if a row was deleted, False if not found.
        """
        with self._session_factory() as session:
            result = session.execute(
                text(
                    "DELETE FROM tenant_configuration "
                    "WHERE tenant_id = :tenant_id AND config_key = :key"
                ),
                {"tenant_id": tenant_id, "key": key},
            )
            session.commit()
            row_count: int = getattr(result, "rowcount", 0)
            return row_count > 0
