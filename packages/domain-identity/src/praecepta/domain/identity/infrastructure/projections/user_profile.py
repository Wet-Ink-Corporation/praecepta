"""Projection for materializing User profile events.

Subscribes to User.Provisioned, User.ProfileUpdated, and
User.PreferencesUpdated events. Maintains the user_profile
projection table via UPSERT pattern.
"""

from __future__ import annotations

from functools import singledispatchmethod
from typing import TYPE_CHECKING, ClassVar

from praecepta.infra.eventsourcing.projections.base import BaseProjection

if TYPE_CHECKING:
    from uuid import UUID

    from eventsourcing.application import ProcessingEvent
    from eventsourcing.domain import DomainEvent

    from praecepta.domain.identity.infrastructure.user_profile_repository import (
        UserProfileRepository,
    )


class UserProfileProjection(BaseProjection):
    """Materializes user events into user_profile projection table.

    Topics: Subscribes to User.Provisioned, User.ProfileUpdated,
            and User.PreferencesUpdated events.
    Pattern: UPSERT into user_profile (idempotent for replay).
    """

    topics: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "praecepta.domain.identity.user:User.Provisioned",
        "praecepta.domain.identity.user:User.ProfileUpdated",
        "praecepta.domain.identity.user:User.PreferencesUpdated",
    )

    def __init__(self, repository: UserProfileRepository) -> None:
        super().__init__()
        self._repo = repository

    @singledispatchmethod
    def policy(
        self,
        domain_event: DomainEvent,
        processing_event: ProcessingEvent[UUID],
    ) -> None:
        """Route events by class name."""
        event_name = domain_event.__class__.__name__
        if event_name == "Provisioned":
            self._handle_provisioned(domain_event)
        elif event_name == "ProfileUpdated":
            self._handle_profile_updated(domain_event)
        elif event_name == "PreferencesUpdated":
            self._handle_preferences_updated(domain_event)

    def _handle_provisioned(self, event: DomainEvent) -> None:
        """UPSERT user profile on provisioning.

        The Provisioned event carries the raw ``name`` parameter, not
        the derived ``display_name``. We replicate the aggregate's
        fallback logic: name -> email prefix -> "User".
        """
        name: str | None = getattr(event, "name", None)
        email: str = getattr(event, "email", "") or ""
        if name:
            display_name = name
        elif email:
            display_name = email.split("@")[0]
        else:
            display_name = "User"

        self._repo.upsert_full(
            user_id=event.originator_id,
            oidc_sub=event.oidc_sub,  # type: ignore[attr-defined]
            email=email,
            display_name=display_name,
            tenant_id=event.tenant_id,  # type: ignore[attr-defined]
            preferences=getattr(event, "preferences", {}),
        )

    def _handle_profile_updated(self, event: DomainEvent) -> None:
        """Update display_name in projection."""
        self._repo.update_display_name(
            user_id=event.originator_id,
            display_name=event.display_name,  # type: ignore[attr-defined]
        )

    def _handle_preferences_updated(self, event: DomainEvent) -> None:
        """Update preferences in projection."""
        self._repo.update_preferences(
            user_id=event.originator_id,
            preferences=event.preferences,  # type: ignore[attr-defined]
        )

    def clear_read_model(self) -> None:
        """TRUNCATE user_profile for rebuild."""
        self._repo.truncate()
