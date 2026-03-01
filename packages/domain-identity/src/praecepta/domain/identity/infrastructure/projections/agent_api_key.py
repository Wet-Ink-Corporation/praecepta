"""Projection for materializing Agent API key events.

Subscribes to Agent.APIKeyIssued and Agent.APIKeyRotated events.
Maintains the agent_api_key_registry projection table via UPSERT pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from eventsourcing.dispatch import singledispatchmethod

from praecepta.domain.identity.agent_app import AgentApplication
from praecepta.infra.eventsourcing.projections.base import BaseProjection

if TYPE_CHECKING:
    from eventsourcing.domain import DomainEvent
    from eventsourcing.persistence import Tracking, TrackingRecorder

    from praecepta.domain.identity.infrastructure.agent_api_key_repository import (
        AgentAPIKeyRepository,
    )


class AgentAPIKeyProjection(BaseProjection):
    """Materializes Agent API key events into agent_api_key_registry projection table.

    Topics: Subscribes to Agent.APIKeyIssued and Agent.APIKeyRotated events.
    Pattern: UPSERT into agent_api_key_registry (idempotent for replay).
    """

    upstream_application: ClassVar[type[Any]] = AgentApplication  # type: ignore[assignment]

    topics: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "praecepta.domain.identity.agent:Agent.APIKeyIssued",
        "praecepta.domain.identity.agent:Agent.APIKeyRotated",
    )

    def __init__(
        self,
        view: TrackingRecorder,
        repository: AgentAPIKeyRepository | None = None,
    ) -> None:
        super().__init__(view=view)
        if repository is None:
            from praecepta.domain.identity.infrastructure.agent_api_key_repository import (
                AgentAPIKeyRepository as _AgentAPIKeyRepository,
            )
            from praecepta.infra.persistence.database import get_sync_session_factory

            repository = _AgentAPIKeyRepository(session_factory=get_sync_session_factory())
        self._repo = repository

    @singledispatchmethod
    def process_event(
        self,
        domain_event: DomainEvent,
        tracking: Tracking,
    ) -> None:
        """Route events by class name."""
        event_name = domain_event.__class__.__name__
        if event_name == "APIKeyIssued":
            self._handle_issued(domain_event)
        elif event_name == "APIKeyRotated":
            self._handle_rotated(domain_event)
        self.view.insert_tracking(tracking)

    def _handle_issued(self, event: DomainEvent) -> None:
        """UPSERT API key on issuance."""
        self._repo.upsert(
            key_id=event.key_id,  # type: ignore[attr-defined]
            agent_id=event.originator_id,
            tenant_id=event.tenant_id,  # type: ignore[attr-defined]
            key_hash=event.key_hash,  # type: ignore[attr-defined]
            status="active",
        )

    def _handle_rotated(self, event: DomainEvent) -> None:
        """Atomically revoke old key and insert new key on rotation."""
        # Revoke old key
        self._repo.update_status(
            key_id=event.revoked_key_id,  # type: ignore[attr-defined]
            status="revoked",
        )

        # Insert new key
        self._repo.upsert(
            key_id=event.new_key_id,  # type: ignore[attr-defined]
            agent_id=event.originator_id,
            tenant_id=event.tenant_id,  # type: ignore[attr-defined]
            key_hash=event.new_key_hash,  # type: ignore[attr-defined]
            status="active",
        )

    def clear_read_model(self) -> None:
        """TRUNCATE agent_api_key_registry for rebuild."""
        self._repo.truncate()
