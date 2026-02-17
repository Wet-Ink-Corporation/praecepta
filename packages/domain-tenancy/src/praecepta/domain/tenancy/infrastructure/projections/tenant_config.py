"""Projection for materializing Tenant.ConfigUpdated events.

Subscribes to ConfigUpdated events and maintains the
tenant_configuration projection table via UPSERT pattern.
"""

from __future__ import annotations

from functools import singledispatchmethod
from typing import TYPE_CHECKING, ClassVar

from praecepta.infra.eventsourcing.projections.base import BaseProjection

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.domain import DomainEvent

    from praecepta.domain.tenancy.infrastructure.config_repository import (
        ConfigRepository,
    )
    from praecepta.foundation.application.config_service import ConfigCache


class TenantConfigProjection(BaseProjection):
    """Materializes configuration events into projection table.

    Topics: Subscribes only to Tenant.ConfigUpdated events.
    Pattern: UPSERT into tenant_configuration (idempotent for replay).
    Invalidation: Clears cache entry for the updated tenant+key.

    Note: Uses class name check instead of singledispatch register
    because eventsourcing library creates event classes dynamically
    via the @event decorator, and mypy cannot resolve them.
    """

    topics: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "praecepta.domain.tenancy.tenant:Tenant.ConfigUpdated",
    )

    def __init__(
        self,
        repository: ConfigRepository,
        cache: ConfigCache | None = None,
    ) -> None:
        super().__init__()
        self._repo = repository
        self._cache = cache

    @singledispatchmethod
    def policy(
        self,
        domain_event: DomainEvent,
        processing_event: ProcessingEvent[UUID],
    ) -> None:
        """Route events by class name.

        The eventsourcing library generates inner event classes dynamically.
        We check the class name to handle ConfigUpdated events.
        """
        if domain_event.__class__.__name__ == "ConfigUpdated":
            self._handle_config_updated(domain_event, processing_event)

    def _handle_config_updated(
        self,
        event: DomainEvent,
        processing_event: ProcessingEvent[UUID],
    ) -> None:
        """Handle Tenant.ConfigUpdated: UPSERT into projection, invalidate cache."""
        self._repo.upsert(
            tenant_id=event.tenant_id,  # type: ignore[attr-defined]
            key=event.config_key,  # type: ignore[attr-defined]
            value=event.config_value,  # type: ignore[attr-defined]
            updated_by=event.updated_by,  # type: ignore[attr-defined]
        )

        # Invalidate cache (sync, in-process only)
        if self._cache is not None:
            ck = self._cache.cache_key(
                event.tenant_id,  # type: ignore[attr-defined]
                event.config_key,  # type: ignore[attr-defined]
            )
            self._cache.delete(ck)

    def clear_read_model(self) -> None:
        """TRUNCATE tenant_configuration for rebuild."""
        with self._repo._session_factory() as session:
            from sqlalchemy import text

            session.execute(text("TRUNCATE TABLE tenant_configuration"))
            session.commit()
