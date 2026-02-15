"""Identifier value objects for type-safe identifier handling.

This module provides strongly-typed identifier value objects that enforce
compile-time type safety and runtime validation across all bounded contexts.

Example:
    >>> from praecepta.foundation.domain import TenantId, UserId
    >>> from uuid import UUID
    >>> tenant = TenantId("acme-corp")
    >>> user = UserId(UUID("550e8400-e29b-41d4-a716-446655440000"))
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True)
class TenantId:
    """Tenant identifier with format validation.

    A value object that wraps a tenant identifier string and validates
    that it conforms to the lowercase alphanumeric slug format.

    Attributes:
        value: Lowercase alphanumeric slug with optional hyphens.

    Raises:
        ValueError: If value doesn't match lowercase slug format.

    Example:
        >>> TenantId("acme-corp")
        TenantId(value='acme-corp')
        >>> TenantId("a")
        TenantId(value='a')
        >>> TenantId("abc-123")
        TenantId(value='abc-123')
    """

    value: str

    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def __post_init__(self) -> None:
        """Validate tenant ID format on construction."""
        if not self._PATTERN.match(self.value):
            msg = (
                f"Invalid tenant ID format: {self.value!r}. "
                "Must be lowercase alphanumeric with hyphens."
            )
            raise ValueError(msg)

    def __str__(self) -> str:
        """Return tenant ID string for serialization."""
        return self.value


@dataclass(frozen=True)
class UserId:
    """User identifier wrapping UUID.

    A value object that wraps a UUID instance for type-safe user identification.
    The UUID must be provided as a UUID object, not a string, to ensure
    proper format validation at the serialization boundary.

    Attributes:
        value: The wrapped UUID instance.

    Example:
        >>> from uuid import UUID
        >>> UserId(UUID("550e8400-e29b-41d4-a716-446655440000"))
        UserId(value=UUID('550e8400-e29b-41d4-a716-446655440000'))
    """

    value: UUID

    def __str__(self) -> str:
        """Return UUID string for serialization."""
        return str(self.value)
