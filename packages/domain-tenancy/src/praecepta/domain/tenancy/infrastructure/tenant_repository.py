"""Repository for tenant list projection (admin/control-plane).

Sync repository (projections use sync pattern).
Unfiltered — no RLS. This is a control-plane concern (admin sees all tenants).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session


class TenantRepository:
    """Read/write access to tenants projection table.

    All methods are synchronous per projection pattern.
    No RLS filtering — this is a control-plane repository.

    Args:
        session_factory: Callable returning a SQLAlchemy Session context manager.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def get(self, slug: str) -> dict[str, Any] | None:
        """Read a single tenant by slug.

        Args:
            slug: Tenant slug identifier.

        Returns:
            Dict with tenant data or None if not found.
        """
        with self._session_factory() as session:
            result = session.execute(
                text(
                    "SELECT id, slug, name, status, "
                    "created_at, activated_at, suspended_at, decommissioned_at "
                    "FROM tenants WHERE slug = :slug"
                ),
                {"slug": slug},
            )
            row = result.fetchone()
            if row is None:
                return None
            return {
                "id": row[0],
                "slug": row[1],
                "name": row[2],
                "status": row[3],
                "created_at": row[4],
                "activated_at": row[5],
                "suspended_at": row[6],
                "decommissioned_at": row[7],
            }

    def list_all(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all tenants, optionally filtered by status.

        Args:
            status: Optional status filter (e.g., "ACTIVE", "SUSPENDED").

        Returns:
            List of tenant dicts ordered by created_at descending.
        """
        with self._session_factory() as session:
            if status is not None:
                result = session.execute(
                    text(
                        "SELECT id, slug, name, status, "
                        "created_at, activated_at, suspended_at, decommissioned_at "
                        "FROM tenants WHERE status = :status "
                        "ORDER BY created_at DESC"
                    ),
                    {"status": status},
                )
            else:
                result = session.execute(
                    text(
                        "SELECT id, slug, name, status, "
                        "created_at, activated_at, suspended_at, decommissioned_at "
                        "FROM tenants ORDER BY created_at DESC"
                    ),
                )
            return [
                {
                    "id": row[0],
                    "slug": row[1],
                    "name": row[2],
                    "status": row[3],
                    "created_at": row[4],
                    "activated_at": row[5],
                    "suspended_at": row[6],
                    "decommissioned_at": row[7],
                }
                for row in result.fetchall()
            ]

    def upsert(
        self,
        tenant_id: str,
        slug: str,
        name: str,
        status: str,
        timestamp: str,
    ) -> None:
        """Insert or update tenant in projection table.

        Uses PostgreSQL UPSERT for idempotent replay.

        Args:
            tenant_id: Aggregate UUID (as string).
            slug: Tenant slug identifier.
            name: Display name.
            status: Current lifecycle status.
            timestamp: ISO 8601 event timestamp.
        """
        with self._session_factory() as session:
            session.execute(
                text(
                    "INSERT INTO tenants (id, slug, name, status, created_at) "
                    "VALUES (:id, :slug, :name, :status, :created_at) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "status = EXCLUDED.status, "
                    "name = EXCLUDED.name"
                ),
                {
                    "id": tenant_id,
                    "slug": slug,
                    "name": name,
                    "status": status,
                    "created_at": timestamp,
                },
            )
            session.commit()

    def update_status(
        self,
        tenant_id: str,
        status: str,
        timestamp_column: str,
        timestamp: str,
    ) -> None:
        """Update tenant status and the corresponding timestamp column.

        Args:
            tenant_id: Aggregate UUID (as string).
            status: New lifecycle status.
            timestamp_column: Column to set (activated_at, suspended_at, decommissioned_at).
            timestamp: ISO 8601 event timestamp.
        """
        allowed_columns = {"activated_at", "suspended_at", "decommissioned_at"}
        if timestamp_column not in allowed_columns:
            msg = f"Invalid timestamp column: {timestamp_column}"
            raise ValueError(msg)

        with self._session_factory() as session:
            session.execute(
                text(
                    f"UPDATE tenants SET status = :status, "
                    f"{timestamp_column} = :timestamp "
                    f"WHERE id = :id"
                ),
                {
                    "id": tenant_id,
                    "status": status,
                    "timestamp": timestamp,
                },
            )
            session.commit()
