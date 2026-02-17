"""Repository for agent_api_key_registry projection table.

Provides sync write methods (used by projection) and sync read
methods (used by authentication middleware).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class AgentAPIKeyRow:
    """Data transfer object for agent_api_key_registry projection row."""

    key_id: str
    agent_id: UUID
    tenant_id: str
    key_hash: str
    status: str
    created_at: datetime
    revoked_at: datetime | None


class AgentAPIKeyRepository:
    """Repository for agent_api_key_registry projection CRUD.

    All methods are sync -- projection and middleware both run synchronously.
    Auth middleware uses lookup_by_key_id() to validate API keys.

    Args:
        session_factory: Callable returning a SQLAlchemy Session context manager.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # -- Sync write methods (projection) --

    def upsert(
        self,
        key_id: str,
        agent_id: UUID,
        tenant_id: str,
        key_hash: str,
        status: str = "active",
    ) -> None:
        """UPSERT API key record (idempotent for event replay).

        Args:
            key_id: 8-char key identifier (PRIMARY KEY).
            agent_id: UUID of owning agent.
            tenant_id: Tenant slug for RLS.
            key_hash: bcrypt hash of secret portion.
            status: 'active', 'pending_revocation', or 'revoked'.
        """
        with self._session_factory() as session:
            session.execute(
                text("""
                    INSERT INTO agent_api_key_registry
                        (key_id, agent_id, tenant_id, key_hash, status, created_at)
                    VALUES
                        (:key_id, :agent_id, :tenant_id, :key_hash, :status, CURRENT_TIMESTAMP)
                    ON CONFLICT (key_id) DO UPDATE SET
                        key_hash = EXCLUDED.key_hash,
                        status = EXCLUDED.status
                """),
                {
                    "key_id": key_id,
                    "agent_id": str(agent_id),
                    "tenant_id": tenant_id,
                    "key_hash": key_hash,
                    "status": status,
                },
            )
            session.commit()

    def update_status(self, key_id: str, status: str) -> None:
        """Update API key status (for revocation).

        Args:
            key_id: 8-char key identifier.
            status: New status ('revoked', etc).
        """
        with self._session_factory() as session:
            session.execute(
                text("""
                    UPDATE agent_api_key_registry
                    SET status = :status,
                        revoked_at = CASE
                            WHEN :status = 'revoked' THEN CURRENT_TIMESTAMP
                            ELSE revoked_at
                        END
                    WHERE key_id = :key_id
                """),
                {"key_id": key_id, "status": status},
            )
            session.commit()

    def truncate(self) -> None:
        """TRUNCATE agent_api_key_registry for projection rebuild."""
        with self._session_factory() as session:
            session.execute(text("DELETE FROM agent_api_key_registry"))
            session.commit()

    # -- Sync read methods (auth middleware) --

    def lookup_by_key_id(self, key_id: str) -> AgentAPIKeyRow | None:
        """Look up API key record by key_id for authentication.

        This query runs WITHOUT RLS enforcement (middleware connection
        bypasses tenant context). Returns None if key not found.

        Args:
            key_id: 8-char key identifier.

        Returns:
            AgentAPIKeyRow or None if key_id not found.
        """
        with self._session_factory() as session:
            result = session.execute(
                text("""
                    SELECT key_id, agent_id, tenant_id, key_hash,
                           status, created_at, revoked_at
                    FROM agent_api_key_registry
                    WHERE key_id = :key_id
                """),
                {"key_id": key_id},
            )
            row = result.fetchone()
            if row is None:
                return None

            from uuid import UUID as _UUID

            return AgentAPIKeyRow(
                key_id=str(row[0]),
                agent_id=_UUID(str(row[1])),
                tenant_id=str(row[2]),
                key_hash=str(row[3]),
                status=str(row[4]),
                created_at=row[5],
                revoked_at=row[6],
            )
