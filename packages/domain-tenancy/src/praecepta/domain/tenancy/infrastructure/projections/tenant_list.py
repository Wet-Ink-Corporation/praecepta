"""Projection for materializing tenant lifecycle events.

Subscribes to Provisioned, Activated, Suspended, Reactivated, and
Decommissioned events. Maintains an unfiltered tenants table for
admin/control-plane use.
"""

from __future__ import annotations

from functools import singledispatchmethod
from typing import TYPE_CHECKING, Any, ClassVar

from praecepta.domain.tenancy.tenant_app import TenantApplication
from praecepta.infra.eventsourcing.projections.base import BaseProjection

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.domain import DomainEvent
    from eventsourcing.utils import EnvType

    from praecepta.domain.tenancy.infrastructure.tenant_repository import (
        TenantRepository,
    )


class TenantListProjection(BaseProjection):
    """Materializes tenant lifecycle events into admin tenants table.

    Topics: Subscribes to all Tenant lifecycle events.
    Pattern: UPSERT/UPDATE into tenants (idempotent for replay).
    Scope: Unfiltered — no RLS. Control-plane concern.

    Note: Uses class name check instead of singledispatch register
    because eventsourcing library creates event classes dynamically
    via the @event decorator.
    """

    upstream_application: ClassVar[type[Any]] = TenantApplication  # type: ignore[assignment]

    topics: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "praecepta.domain.tenancy.tenant:Tenant.Provisioned",
        "praecepta.domain.tenancy.tenant:Tenant.Activated",
        "praecepta.domain.tenancy.tenant:Tenant.Suspended",
        "praecepta.domain.tenancy.tenant:Tenant.Reactivated",
        "praecepta.domain.tenancy.tenant:Tenant.Decommissioned",
    )

    def __init__(
        self,
        repository: TenantRepository | None = None,
        env: EnvType | None = None,
    ) -> None:
        super().__init__(env=env)
        if repository is None:
            from praecepta.domain.tenancy.infrastructure.tenant_repository import (
                TenantRepository as _TenantRepository,
            )
            from praecepta.infra.persistence.database import get_sync_session_factory

            repository = _TenantRepository(session_factory=get_sync_session_factory())
        self._repo = repository

    @singledispatchmethod
    def policy(
        self,
        domain_event: DomainEvent,
        processing_event: ProcessingEvent[UUID],
    ) -> None:
        """Route events by class name."""
        event_name = domain_event.__class__.__name__
        handler = self._handlers.get(event_name)
        if handler is not None:
            handler(self, domain_event)

    _handlers: ClassVar[dict[str, object]] = {}

    def _handle_provisioned(self, event: DomainEvent) -> None:
        """Handle Tenant.Provisioned: INSERT into tenants table."""
        self._repo.upsert(
            tenant_id=str(event.originator_id),
            slug=event.slug,  # type: ignore[attr-defined]
            name=event.name,  # type: ignore[attr-defined]
            status="PROVISIONING",
            timestamp=event.timestamp.isoformat() if event.timestamp else "",
        )

    def _handle_activated(self, event: DomainEvent) -> None:
        """Handle Tenant.Activated: UPDATE status to ACTIVE."""
        self._repo.update_status(
            tenant_id=str(event.originator_id),
            status="ACTIVE",
            timestamp_column="activated_at",
            timestamp=event.timestamp.isoformat() if event.timestamp else "",
        )

    def _handle_suspended(self, event: DomainEvent) -> None:
        """Handle Tenant.Suspended: UPDATE status to SUSPENDED."""
        self._repo.update_status(
            tenant_id=str(event.originator_id),
            status="SUSPENDED",
            timestamp_column="suspended_at",
            timestamp=event.timestamp.isoformat() if event.timestamp else "",
        )

    def _handle_reactivated(self, event: DomainEvent) -> None:
        """Handle Tenant.Reactivated: UPDATE status back to ACTIVE."""
        self._repo.update_status(
            tenant_id=str(event.originator_id),
            status="ACTIVE",
            timestamp_column="activated_at",
            timestamp=event.timestamp.isoformat() if event.timestamp else "",
        )

    def _handle_decommissioned(self, event: DomainEvent) -> None:
        """Handle Tenant.Decommissioned: UPDATE status to DECOMMISSIONED."""
        self._repo.update_status(
            tenant_id=str(event.originator_id),
            status="DECOMMISSIONED",
            timestamp_column="decommissioned_at",
            timestamp=event.timestamp.isoformat() if event.timestamp else "",
        )

    def clear_read_model(self) -> None:
        """TRUNCATE tenants table for rebuild."""
        with self._repo._session_factory() as session:
            from sqlalchemy import text

            session.execute(text("TRUNCATE TABLE tenants"))
            session.commit()


# Register handlers by event class name
TenantListProjection._handlers = {
    "Provisioned": TenantListProjection._handle_provisioned,
    "Activated": TenantListProjection._handle_activated,
    "Suspended": TenantListProjection._handle_suspended,
    "Reactivated": TenantListProjection._handle_reactivated,
    "Decommissioned": TenantListProjection._handle_decommissioned,
}
