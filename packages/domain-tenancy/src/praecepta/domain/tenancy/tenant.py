"""Tenant aggregate with lifecycle state machine.

Event-sourced aggregate managing tenant lifecycle transitions and
per-tenant configuration storage. Config key/value validation is
the consumer's responsibility — the aggregate stores any key/value
pair when in ACTIVE state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.domain import event
from pydantic import BaseModel

from praecepta.foundation.domain.aggregates import BaseAggregate
from praecepta.foundation.domain.exceptions import (
    InvalidStateTransitionError,
)
from praecepta.foundation.domain.tenant_value_objects import (
    TenantName,
    TenantSlug,
    TenantStatus,
)

if TYPE_CHECKING:
    from typing import Any


class Tenant(BaseAggregate):
    """Event-sourced Tenant aggregate with lifecycle state machine.

    State machine::

                    activate()
        PROVISIONING -----------------> ACTIVE
                                          |  ^
                              suspend()   |  |  reactivate()
                                          v  |
                                       SUSPENDED
                                          |
                      decommission()      |  decommission()
                                          v
              ACTIVE ---------> DECOMMISSIONED (terminal)

    Attributes:
        tenant_id: Immutable slug identifier (must match slug at provisioning).
        name: Human-readable display name.
        slug: Validated tenant slug.
        status: Current lifecycle state (TenantStatus enum value).
        config: Arbitrary configuration dictionary.
        metadata: Extensible profile data (company info, locale, etc.).
        suspension_reason: Reason for most recent suspension (if any).
        suspension_category: Machine-readable suspension category (if any).
        decommission_reason: Reason for decommissioning (if any).
    """

    # -- Creation (records Tenant.Provisioned event) -------------------------

    @event("Provisioned")
    def __init__(
        self,
        *,
        tenant_id: str,
        name: str,
        slug: str,
        config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Create a new Tenant in PROVISIONING state.

        Args:
            tenant_id: Tenant identifier (must equal slug — enforced).
            name: Human-readable display name (1-255 chars, stripped).
            slug: Unique tenant slug (lowercase alphanumeric + hyphens, 2-63 chars).
            config: Optional initial configuration dictionary.
            metadata: Optional initial profile metadata dictionary.

        Raises:
            ValueError: If slug or name fails validation, or if
                tenant_id does not match slug.
        """
        validated_slug = TenantSlug(slug)
        validated_name = TenantName(name)

        if tenant_id != validated_slug.value:
            msg = (
                f"tenant_id must match slug: "
                f"got tenant_id='{tenant_id}', slug='{validated_slug.value}'"
            )
            raise ValueError(msg)

        self.tenant_id: str = validated_slug.value
        self.name: str = validated_name.value
        self.slug: str = validated_slug.value
        self.status: str = TenantStatus.PROVISIONING.value
        self.config: dict[str, Any] = config or {}
        self.metadata: dict[str, Any] = metadata or {}
        self.suspension_reason: str | None = None
        self.suspension_category: str | None = None
        self.decommission_reason: str | None = None

    # -- Public command methods (validate then delegate) --------------------

    def request_activate(
        self,
        initiated_by: str,
        correlation_id: str | None = None,
    ) -> None:
        """Activate a provisioning tenant. PROVISIONING -> ACTIVE.

        Idempotent: calling on an already-ACTIVE tenant is a no-op.

        Args:
            initiated_by: User ID of the operator performing the action.
            correlation_id: Optional request/workflow tracing ID.

        Raises:
            InvalidStateTransitionError: If current state is not PROVISIONING
                (and not already ACTIVE for idempotency).
        """
        if self.status == TenantStatus.ACTIVE.value:
            return  # idempotent
        if self.status != TenantStatus.PROVISIONING.value:
            raise InvalidStateTransitionError(
                f"Cannot activate tenant {self.id}: "
                f"current state is {self.status}, expected PROVISIONING"
            )
        self._apply_activate(
            initiated_by=initiated_by,
            correlation_id=correlation_id or "",
        )

    def request_suspend(
        self,
        initiated_by: str,
        reason: str | None = None,
        category: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Suspend an active tenant. ACTIVE -> SUSPENDED.

        Idempotent: calling on an already-SUSPENDED tenant is a no-op.

        Args:
            initiated_by: User ID of the operator performing the action.
            reason: Optional human-readable suspension reason.
            category: Optional machine-readable suspension category.
                Common values: "admin_action", "billing_hold",
                "security_review", "terms_violation".
            correlation_id: Optional request/workflow tracing ID.

        Raises:
            InvalidStateTransitionError: If current state is not ACTIVE
                (and not already SUSPENDED for idempotency).
        """
        if self.status == TenantStatus.SUSPENDED.value:
            return  # idempotent
        if self.status != TenantStatus.ACTIVE.value:
            raise InvalidStateTransitionError(
                f"Cannot suspend tenant {self.id}: current state is {self.status}, expected ACTIVE"
            )
        self._apply_suspend(
            reason=reason or "",
            category=category or "",
            initiated_by=initiated_by,
            correlation_id=correlation_id or "",
        )

    def request_reactivate(
        self,
        initiated_by: str,
        correlation_id: str | None = None,
    ) -> None:
        """Reactivate a suspended tenant. SUSPENDED -> ACTIVE.

        Idempotent: calling on an already-ACTIVE tenant is a no-op.

        Args:
            initiated_by: User ID of the operator performing the action.
            correlation_id: Optional request/workflow tracing ID.

        Raises:
            InvalidStateTransitionError: If current state is not SUSPENDED
                (and not already ACTIVE for idempotency).
        """
        if self.status == TenantStatus.ACTIVE.value:
            return  # idempotent
        if self.status != TenantStatus.SUSPENDED.value:
            raise InvalidStateTransitionError(
                f"Cannot reactivate tenant {self.id}: "
                f"current state is {self.status}, expected SUSPENDED"
            )
        self._apply_reactivate(
            initiated_by=initiated_by,
            correlation_id=correlation_id or "",
        )

    def request_decommission(
        self,
        initiated_by: str,
        reason: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Decommission a tenant (terminal). ACTIVE|SUSPENDED -> DECOMMISSIONED.

        Idempotent: calling on an already-DECOMMISSIONED tenant is a no-op.

        Args:
            initiated_by: User ID of the operator performing the action.
            reason: Optional human-readable decommission reason.
            correlation_id: Optional request/workflow tracing ID.

        Raises:
            InvalidStateTransitionError: If current state is not ACTIVE or SUSPENDED
                (and not already DECOMMISSIONED for idempotency).
        """
        if self.status == TenantStatus.DECOMMISSIONED.value:
            return  # idempotent
        if self.status not in (
            TenantStatus.ACTIVE.value,
            TenantStatus.SUSPENDED.value,
        ):
            raise InvalidStateTransitionError(
                f"Cannot decommission tenant {self.id}: "
                f"current state is {self.status}, expected ACTIVE or SUSPENDED"
            )
        self._apply_decommission(
            reason=reason or "",
            initiated_by=initiated_by,
            correlation_id=correlation_id or "",
        )

    def request_update_config(
        self,
        config_key: str,
        config_value: dict[str, Any] | BaseModel,
        updated_by: str,
    ) -> None:
        """Update a single configuration entry.

        Only ACTIVE tenants can have configuration updated. Config key/value
        validation is the consumer's responsibility — the aggregate stores
        any key/value pair.

        Args:
            config_key: Configuration key string.
            config_value: ConfigValue Pydantic model or pre-serialized dict.
                If a Pydantic BaseModel is passed, model_dump() is called
                automatically.
            updated_by: Operator user ID for audit trail.

        Raises:
            InvalidStateTransitionError: If tenant is not ACTIVE.
        """
        if self.status != TenantStatus.ACTIVE.value:
            raise InvalidStateTransitionError(
                f"Cannot update config for tenant {self.id}: "
                f"current state is {self.status}, expected ACTIVE"
            )
        serialized: dict[str, Any] = (
            config_value.model_dump() if isinstance(config_value, BaseModel) else config_value
        )
        self._apply_config_updated(
            tenant_id=self.tenant_id,
            config_key=config_key,
            config_value=serialized,
            updated_by=updated_by,
        )

    def request_update_metadata(
        self,
        metadata: dict[str, Any],
        updated_by: str,
    ) -> None:
        """Update tenant profile metadata.

        Merges the provided metadata dict into the existing metadata.
        Only ACTIVE tenants can have metadata updated.

        Args:
            metadata: Dictionary of profile data to merge (e.g., company,
                timezone, locale, region, contact_email).
            updated_by: Operator user ID for audit trail.

        Raises:
            InvalidStateTransitionError: If tenant is not ACTIVE.
        """
        if self.status != TenantStatus.ACTIVE.value:
            raise InvalidStateTransitionError(
                f"Cannot update metadata for tenant {self.id}: "
                f"current state is {self.status}, expected ACTIVE"
            )
        self._apply_metadata_updated(
            metadata=metadata,
            updated_by=updated_by,
        )

    def record_data_deleted(
        self,
        category: str,
        entity_count: int,
        deleted_by: str,
    ) -> None:
        """Record audit event for cascade deletion phase.

        This is an audit-only event -- no aggregate state changes.
        Called by decommission handlers after each cascade phase
        completes. Must only be called on DECOMMISSIONED tenants.

        Args:
            category: Data category deleted (e.g., "slug_reservation", "projections").
            entity_count: Number of entities affected.
            deleted_by: User ID of operator or "system".

        Raises:
            InvalidStateTransitionError: If tenant is not DECOMMISSIONED.
        """
        if self.status != TenantStatus.DECOMMISSIONED.value:
            raise InvalidStateTransitionError(
                f"Cannot record data deletion for tenant {self.id}: "
                f"current state is {self.status}, expected DECOMMISSIONED"
            )
        self._apply_data_deleted(
            category=category,
            entity_count=entity_count,
            deleted_by=deleted_by,
        )

    # -- Private @event mutators -------------------------------------------

    @event("Activated")
    def _apply_activate(self, initiated_by: str, correlation_id: str) -> None:
        self.status = TenantStatus.ACTIVE.value

    @event("Suspended")
    def _apply_suspend(
        self,
        reason: str,
        category: str,
        initiated_by: str,
        correlation_id: str,
    ) -> None:
        self.status = TenantStatus.SUSPENDED.value
        self.suspension_reason = reason if reason else None
        self.suspension_category = category if category else None

    @event("Reactivated")
    def _apply_reactivate(self, initiated_by: str, correlation_id: str) -> None:
        self.status = TenantStatus.ACTIVE.value
        self.suspension_reason = None
        self.suspension_category = None

    @event("Decommissioned")
    def _apply_decommission(
        self,
        reason: str,
        initiated_by: str,
        correlation_id: str,
    ) -> None:
        self.status = TenantStatus.DECOMMISSIONED.value
        self.decommission_reason = reason if reason else None

    @event("ConfigUpdated")
    def _apply_config_updated(
        self,
        tenant_id: str,
        config_key: str,
        config_value: dict[str, Any],
        updated_by: str,
    ) -> None:
        """Apply configuration update to aggregate state.

        Records Tenant.ConfigUpdated event for:
        - Projection materialization (tenant_configuration table)
        - Cache invalidation
        - Audit trail

        Args:
            tenant_id: Tenant slug (included in event for projection use).
            config_key: Configuration key string.
            config_value: Serialized ConfigValue dict.
            updated_by: Operator user ID.
        """
        self.config[config_key] = config_value

    @event("MetadataUpdated")
    def _apply_metadata_updated(
        self,
        metadata: dict[str, Any],
        updated_by: str,
    ) -> None:
        """Apply metadata update by merging into existing metadata."""
        self.metadata.update(metadata)

    @event("DataDeleted")
    def _apply_data_deleted(self, category: str, entity_count: int, deleted_by: str) -> None:
        """Audit-only event -- no aggregate state changes."""
        pass  # No state mutation; event recording is the purpose
