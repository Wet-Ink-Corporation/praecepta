"""Event-sourced User aggregate for OIDC-provisioned users.

Immutable identity claims from OIDC (oidc_sub, email, tenant_id)
vs mutable local properties (display_name, preferences).
"""

from __future__ import annotations

from typing import Any

from eventsourcing.domain import event

from praecepta.foundation.domain.aggregates import BaseAggregate
from praecepta.foundation.domain.user_value_objects import DisplayName, Email, OidcSub


class User(BaseAggregate):
    """Event-sourced User aggregate with OIDC claims mapping.

    Attributes:
        oidc_sub: OIDC subject identifier (immutable, unique per IdP).
        email: Email from OIDC claims (immutable, may be empty).
        tenant_id: Tenant slug (immutable, inherited from BaseAggregate).
        display_name: User-customizable display name (mutable).
        preferences: User preferences as JSON dict (mutable).
    """

    # -- Creation (records User.Provisioned event) --

    @event("Provisioned")
    def __init__(
        self,
        *,
        oidc_sub: str,
        tenant_id: str,
        email: str | None = None,
        name: str | None = None,
    ) -> None:
        """Create a new User from OIDC claims.

        Args:
            oidc_sub: OIDC subject identifier (required, validated).
            tenant_id: Tenant slug (required).
            email: Email from OIDC claims (optional, defaults to "").
            name: Name from OIDC claims (optional, used for display_name derivation).

        Raises:
            ValueError: If oidc_sub is empty or invalid format.
        """
        # Validate via value objects
        validated_sub = OidcSub(oidc_sub)
        validated_email = Email(email or "")

        # Set immutable properties
        self.oidc_sub: str = validated_sub.value
        self.email: str = validated_email.value
        self.tenant_id: str = tenant_id

        # Derive display_name with fallback chain
        if name:
            self.display_name: str = name
        elif email:
            self.display_name = email.split("@")[0]
        else:
            self.display_name = "User"

        # Initialize mutable properties
        self.preferences: dict[str, Any] = {}

    # -- Public command methods --

    def request_update_display_name(self, display_name: str) -> None:
        """Update display name with validation.

        Args:
            display_name: New display name (non-empty, max 255 chars).

        Raises:
            ValueError: If display_name is empty or whitespace-only.
        """
        validated = DisplayName(display_name)
        self._apply_profile_updated(display_name=validated.value)

    def request_update_preferences(self, preferences: dict[str, Any]) -> None:
        """Update user preferences.

        Args:
            preferences: New preferences dict (replaces existing).
        """
        self._apply_preferences_updated(preferences=preferences)

    # -- Private @event mutators --

    @event("ProfileUpdated")
    def _apply_profile_updated(self, display_name: str) -> None:
        self.display_name = display_name

    @event("PreferencesUpdated")
    def _apply_preferences_updated(self, preferences: dict[str, Any]) -> None:
        self.preferences = preferences
