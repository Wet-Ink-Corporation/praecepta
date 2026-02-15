"""Value objects for the User aggregate.

Immutable, validated domain primitives. All validation occurs at construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class OidcSub:
    """Validated OIDC subject identifier.

    Format: Non-empty string, max 255 characters (per OpenID Connect Core 1.0).
    No format constraints beyond non-empty to support multiple IdPs.

    Attributes:
        value: The validated OIDC sub string.

    Raises:
        ValueError: If sub is empty or exceeds 255 characters.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            msg = "OIDC sub cannot be empty"
            raise ValueError(msg)
        if len(self.value) > 255:
            msg = f"OIDC sub too long: {len(self.value)} chars (max 255)"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class Email:
    """Validated email address value object.

    Format: Basic email validation (contains @ and domain) if non-empty.
    Empty string is explicitly valid (optional OIDC claim).

    Attributes:
        value: The validated email string or empty string.

    Raises:
        ValueError: If email is non-empty but invalid format or exceeds 255 chars.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            return  # Empty is valid (optional claim)
        if len(self.value) > 255:
            msg = f"Email too long: {len(self.value)} chars (max 255)"
            raise ValueError(msg)
        if not _EMAIL_PATTERN.match(self.value):
            msg = f"Invalid email format: '{self.value}'"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DisplayName:
    """Validated display name value object.

    Format: Non-empty string after whitespace stripping, max 255 characters.
    Leading and trailing whitespace is automatically removed.

    Attributes:
        value: The validated display name string (whitespace stripped).

    Raises:
        ValueError: If display name is empty/whitespace-only or exceeds 255 chars.
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            msg = "Display name cannot be empty"
            raise ValueError(msg)
        if len(stripped) > 255:
            msg = f"Display name too long: {len(stripped)} chars (max 255)"
            raise ValueError(msg)
        object.__setattr__(self, "value", stripped)
