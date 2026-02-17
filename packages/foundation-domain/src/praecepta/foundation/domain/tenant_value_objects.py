"""Value objects for the Tenant aggregate.

Immutable, validated domain primitives. All validation occurs at
construction time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class TenantStatus(StrEnum):
    """Tenant lifecycle states.

    Four-state lifecycle matching the Tenant aggregate state machine:
        PROVISIONING -> ACTIVE <-> SUSPENDED -> DECOMMISSIONED

    Uses StrEnum for native JSON serialization.
    """

    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DECOMMISSIONED = "DECOMMISSIONED"


class SuspensionCategory(StrEnum):
    """Machine-readable suspension categories.

    Consumers can use these to drive automated remediation workflows
    (e.g., auto-reactivate on payment for BILLING_HOLD).

    This is a base set — consumers may pass any string value as a
    category. These constants provide well-known defaults.
    """

    ADMIN_ACTION = "admin_action"
    BILLING_HOLD = "billing_hold"
    SECURITY_REVIEW = "security_review"
    TERMS_VIOLATION = "terms_violation"
    OTHER = "other"


_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


@dataclass(frozen=True, slots=True)
class TenantSlug:
    """Validated tenant slug (immutable after creation).

    Format: lowercase alphanumeric + hyphens, 2-63 chars.
    Must start and end with alphanumeric character.

    Attributes:
        value: The validated slug string.

    Raises:
        ValueError: If slug does not meet format or length requirements.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) < 2:
            msg = f"Tenant slug too short: '{self.value}' (min 2 chars)"
            raise ValueError(msg)
        if len(self.value) > 63:
            msg = f"Tenant slug too long: '{self.value}' (max 63 chars)"
            raise ValueError(msg)
        if not _SLUG_PATTERN.match(self.value):
            msg = (
                f"Invalid tenant slug '{self.value}': must be lowercase "
                "alphanumeric with hyphens, starting and ending with alphanumeric"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class TenantName:
    """Validated tenant display name.

    Attributes:
        value: The validated name string (1-255 chars, unicode OK).

    Raises:
        ValueError: If name is empty, whitespace-only, or exceeds 255 chars.
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            msg = "Tenant name cannot be empty"
            raise ValueError(msg)
        if len(stripped) > 255:
            msg = f"Tenant name too long: {len(stripped)} chars (max 255)"
            raise ValueError(msg)
        # Store the stripped value (bypass frozen with object.__setattr__)
        object.__setattr__(self, "value", stripped)
