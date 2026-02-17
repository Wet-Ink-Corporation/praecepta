"""Repository for user_profile projection table.

Provides sync write methods (used by projection) and async read
methods (used by query endpoints).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class UserProfileRow:
    """Data transfer object for user_profile projection row."""

    user_id: UUID
    oidc_sub: str
    email: str
    display_name: str
    tenant_id: str
    preferences: dict[str, Any]
    created_at: datetime


class UserProfileRepository:
    """Repository for user_profile projection CRUD.

    Write methods (upsert, update) are sync -- called by projection.
    Read methods (get_by_*) are async -- called by query endpoints.

    Args:
        session_factory: Callable returning a SQLAlchemy Session context manager.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # -- Sync write methods (projection) --

    def upsert_full(
        self,
        user_id: UUID,
        oidc_sub: str,
        email: str,
        display_name: str,
        tenant_id: str,
        preferences: dict[str, Any],
    ) -> None:
        """UPSERT full user profile (idempotent for event replay)."""
        with self._session_factory() as session:
            session.execute(
                text("""
                    INSERT INTO user_profile
                        (user_id, oidc_sub, email, display_name,
                         tenant_id, preferences, created_at, updated_at)
                    VALUES
                        (:user_id, :oidc_sub, :email, :display_name,
                         :tenant_id, :preferences, NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        email = EXCLUDED.email,
                        display_name = EXCLUDED.display_name,
                        preferences = EXCLUDED.preferences,
                        updated_at = NOW()
                """),
                {
                    "user_id": str(user_id),
                    "oidc_sub": oidc_sub,
                    "email": email,
                    "display_name": display_name,
                    "tenant_id": tenant_id,
                    "preferences": json.dumps(preferences),
                },
            )
            session.commit()

    def update_display_name(self, user_id: UUID, display_name: str) -> None:
        """Update display_name in projection."""
        with self._session_factory() as session:
            session.execute(
                text("""
                    UPDATE user_profile
                    SET display_name = :display_name, updated_at = NOW()
                    WHERE user_id = :user_id
                """),
                {"user_id": str(user_id), "display_name": display_name},
            )
            session.commit()

    def update_preferences(self, user_id: UUID, preferences: dict[str, Any]) -> None:
        """Update preferences in projection."""
        with self._session_factory() as session:
            session.execute(
                text("""
                    UPDATE user_profile
                    SET preferences = :preferences, updated_at = NOW()
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": str(user_id),
                    "preferences": json.dumps(preferences),
                },
            )
            session.commit()

    def truncate(self) -> None:
        """TRUNCATE user_profile for projection rebuild."""
        with self._session_factory() as session:
            session.execute(text("TRUNCATE TABLE user_profile"))
            session.commit()

    # -- Async read methods (query endpoints) --

    async def get_by_user_id(self, user_id: UUID, tenant_id: str) -> UserProfileRow | None:
        """Get user profile by user_id and tenant_id.

        Runs sync query in thread pool via asyncio.to_thread.
        """
        import asyncio
        from functools import partial

        return await asyncio.to_thread(partial(self._get_by_user_id_sync, user_id, tenant_id))

    def _get_by_user_id_sync(self, user_id: UUID, tenant_id: str) -> UserProfileRow | None:
        """Sync implementation of get_by_user_id."""
        with self._session_factory() as session:
            result = session.execute(
                text("""
                    SELECT user_id, oidc_sub, email, display_name,
                           tenant_id, preferences, created_at
                    FROM user_profile
                    WHERE user_id = :user_id AND tenant_id = :tenant_id
                """),
                {"user_id": str(user_id), "tenant_id": tenant_id},
            )
            row = result.fetchone()
            if row is None:
                return None

            from uuid import UUID as _UUID

            return UserProfileRow(
                user_id=_UUID(str(row[0])),
                oidc_sub=str(row[1]),
                email=str(row[2]),
                display_name=str(row[3]),
                tenant_id=str(row[4]),
                preferences=(json.loads(row[5]) if isinstance(row[5], str) else row[5]),
                created_at=row[6],
            )

    @classmethod
    def ensure_table_exists(cls, session_factory: Callable[[], Session]) -> None:
        """Create user_profile table if it does not exist."""
        with session_factory() as session:
            session.execute(
                text("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    user_id UUID PRIMARY KEY,
                    oidc_sub VARCHAR(255) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL DEFAULT '',
                    display_name VARCHAR(255) NOT NULL DEFAULT 'User',
                    tenant_id VARCHAR(63) NOT NULL,
                    preferences JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_user_profile_oidc_sub_tenant
                    ON user_profile (oidc_sub, tenant_id);

                CREATE INDEX IF NOT EXISTS idx_user_profile_tenant
                    ON user_profile (tenant_id);

                -- RLS policy for tenant isolation
                ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY;
                ALTER TABLE user_profile FORCE ROW LEVEL SECURITY;

                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE tablename = 'user_profile'
                        AND policyname = 'tenant_isolation_user_profile'
                    ) THEN
                        CREATE POLICY tenant_isolation_user_profile
                            ON user_profile
                            USING (tenant_id = current_setting('app.current_tenant', true));
                    END IF;
                END
                $$;
            """)
            )
            session.commit()
