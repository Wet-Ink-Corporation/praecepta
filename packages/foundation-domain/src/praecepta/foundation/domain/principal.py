"""Principal value object representing an authenticated identity.

Pure domain object with no external dependencies. Immutable (frozen dataclass).
Extracted from validated JWT claims by the auth middleware + dependency layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class PrincipalType(StrEnum):
    """Type of authenticated principal."""

    USER = "user"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated entity performing a request.

    Constructed from validated JWT claims. Immutable for thread safety
    and to prevent modification after extraction.

    Attributes:
        subject: JWT 'sub' claim -- unique principal identifier from identity provider.
        tenant_id: Tenant slug from JWT 'tenant_id' custom claim.
        user_id: UUID parsed from 'sub' claim.
        roles: Role strings from JWT 'roles' claim. Empty tuple if absent.
        email: Email from JWT 'email' claim. None if absent.
        principal_type: USER or AGENT. Defaults to USER.
    """

    subject: str
    tenant_id: str
    user_id: UUID
    roles: tuple[str, ...] = ()
    email: str | None = None
    principal_type: PrincipalType = PrincipalType.USER
