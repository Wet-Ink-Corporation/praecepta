"""Value objects for the Agent aggregate.

Immutable, validated domain primitives. All validation occurs at construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_AGENT_TYPE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?$")

# Default API key prefix. Applications may override this via the
# APIKeyGeneratorPort implementation.
DEFAULT_API_KEY_PREFIX = "pk_"


class AgentStatus(StrEnum):
    """Agent lifecycle status.

    States:
        ACTIVE: Agent is operational and can authenticate.
        SUSPENDED: Agent is temporarily disabled.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"


@dataclass(frozen=True, slots=True)
class AgentTypeId:
    """Validated agent type identifier.

    Format: lowercase alphanumeric + hyphens + underscores, 2-63 chars.
    Must start and end with alphanumeric (no leading/trailing hyphens/underscores).

    Examples:
        - "workflow-bot"
        - "data-ingestion"
        - "mcp-server"
        - "my_test_agent"

    Attributes:
        value: The validated agent type ID string.

    Raises:
        ValueError: If format is invalid or length out of bounds.
    """

    value: str

    def __post_init__(self) -> None:
        if not (2 <= len(self.value) <= 63):
            msg = f"Agent type ID must be 2-63 characters, got {len(self.value)}"
            raise ValueError(msg)
        if not _AGENT_TYPE_ID_PATTERN.match(self.value):
            msg = (
                f"Invalid agent type ID format: '{self.value}'. "
                "Must be lowercase alphanumeric + hyphens/underscores, "
                "starting and ending with alphanumeric."
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class APIKeyMetadata:
    """API key metadata (NO plaintext secrets).

    The aggregate stores this metadata for key lifecycle tracking,
    but never stores plaintext keys.

    Attributes:
        key_id: Identifier portion of the key (stored unhashed for lookup).
        key_hash: Hash of secret portion (NEVER plaintext).
        created_at: ISO 8601 timestamp string.
        status: "active" | "pending_revocation" | "revoked".
    """

    key_id: str
    key_hash: str
    created_at: str
    status: str
