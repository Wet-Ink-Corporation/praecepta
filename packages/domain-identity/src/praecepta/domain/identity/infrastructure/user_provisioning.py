"""User provisioning service for JIT (Just-In-Time) user creation.

Orchestrates the idempotent provisioning flow:
1. Fast-path: Check if user already exists (registry lookup)
2. Slow-path: Reserve OIDC sub -> Create User aggregate -> Confirm reservation
3. Race condition handling: Retry lookup on ConflictError
4. Compensating action: Release reservation on any creation failure
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from praecepta.domain.identity.user import User
from praecepta.foundation.domain.exceptions import ConflictError

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.application import Application

    from praecepta.domain.identity.infrastructure.oidc_sub_registry import (
        OidcSubRegistry,
    )

logger = logging.getLogger(__name__)


class UserProvisioningService:
    """Orchestrates idempotent User aggregate provisioning from OIDC claims.

    Attributes:
        _app: UserApplication for aggregate persistence.
        _registry: OidcSubRegistry for uniqueness enforcement.
    """

    def __init__(
        self,
        app: Application[UUID],
        registry: OidcSubRegistry,
    ) -> None:
        self._app = app
        self._registry = registry

    def ensure_user_exists(
        self,
        oidc_sub: str,
        tenant_id: str,
        email: str | None = None,
        name: str | None = None,
    ) -> UUID:
        """Provision user if not exists. Idempotent, handles race conditions.

        Flow:
        1. Fast-path: lookup() -> return existing user_id if found
        2. Slow-path:
           - reserve(oidc_sub, tenant_id)
           - Create User aggregate
           - app.save(user)
           - confirm(oidc_sub, user.id)
        3. On ConflictError: retry lookup (race condition)
        4. On any error during creation: release(oidc_sub) (compensating action)

        Args:
            oidc_sub: OIDC subject identifier (required).
            tenant_id: Tenant slug (required).
            email: Email from OIDC claims (optional).
            name: Name from OIDC claims (optional, used for display_name).

        Returns:
            UUID of the User aggregate (existing or newly created).

        Raises:
            ConflictError: If race condition handling fails (unexpected).
            ValueError: If User aggregate validation fails (invalid oidc_sub/email).
            RuntimeError: If event store save fails.
        """
        # 1. Fast-path: Check if user already exists
        existing_user_id = self._registry.lookup(oidc_sub)
        if existing_user_id is not None:
            existing_user: User = self._app.repository.get(existing_user_id)
            if existing_user.tenant_id != tenant_id:
                raise ConflictError(
                    f"OIDC sub '{oidc_sub}' is already provisioned for a different tenant",
                    oidc_sub=oidc_sub,
                )
            logger.debug(
                "user_provisioning_skipped",
                extra={"oidc_sub": oidc_sub, "user_id": str(existing_user_id)},
            )
            return existing_user_id

        # 2. Slow-path: Provision new user
        logger.debug(
            "user_provisioning_started",
            extra={"oidc_sub": oidc_sub, "tenant_id": tenant_id},
        )

        # 2a. Reserve OIDC sub
        try:
            self._registry.reserve(oidc_sub, tenant_id)
        except ConflictError:
            logger.warning(
                "user_provisioning_race_condition",
                extra={"oidc_sub": oidc_sub, "conflict_type": "reserve"},
            )
            for attempt in range(5):
                retry_user_id = self._registry.lookup(oidc_sub)
                if retry_user_id is not None:
                    return retry_user_id
                time.sleep(0.05 * (attempt + 1))
            raise

        # 2b. Create User aggregate and save (with compensating action on failure)
        try:
            user = User(
                oidc_sub=oidc_sub,
                tenant_id=tenant_id,
                email=email,
                name=name,
            )
            self._app.save(user)

            # 2c. Confirm reservation with aggregate UUID
            self._registry.confirm(oidc_sub, user.id)

            logger.info(
                "user_provisioned",
                extra={
                    "oidc_sub": oidc_sub,
                    "user_id": str(user.id),
                    "tenant_id": tenant_id,
                },
            )
            return user.id

        except Exception:
            self._registry.release(oidc_sub)
            logger.exception(
                "user_provisioning_failed_releasing_reservation",
                extra={"oidc_sub": oidc_sub, "tenant_id": tenant_id},
            )
            raise
