"""Command and handler for rotating API keys."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from praecepta.foundation.domain.ports.api_key_generator import (
        APIKeyGeneratorPort,
    )

logger = logging.getLogger(__name__)


class EventSourcedApplication(Protocol):
    """Protocol for an event sourcing application.

    Provides repository access and save operations for aggregates.
    Implementations live in infrastructure packages.
    """

    @property
    def repository(self) -> Any: ...

    def save(self, aggregate: Any) -> None: ...


@dataclass(frozen=True)
class RotateAPIKeyCommand:
    """Command to atomically rotate an agent's API key."""

    agent_id: UUID
    requested_by: str  # Principal subject


@dataclass(frozen=True)
class RotateAPIKeyResult:
    """Result of API key rotation (display-once)."""

    key_id: str
    api_key: str  # Full plaintext key: {prefix}_{key_id}{secret}
    warning: str = "Save this key immediately. You will not be able to view it again."


class RotateAPIKeyHandler:
    """Rotates API key atomically: generate new, revoke old.

    Security invariant: Same as IssueAPIKeyHandler -- plaintext only in
    return value, never logged/persisted.
    """

    def __init__(
        self,
        app: EventSourcedApplication,
        key_generator: APIKeyGeneratorPort,
    ) -> None:
        """Initialize handler with application and key generator.

        Args:
            app: Event sourcing application for aggregates.
            key_generator: Port for API key generation and hashing.
        """
        self._app = app
        self._key_gen = key_generator

    def handle(self, cmd: RotateAPIKeyCommand) -> RotateAPIKeyResult:
        """Rotate API key for agent.

        Returns:
            RotateAPIKeyResult with new plaintext key.

        Raises:
            AggregateNotFoundError: If agent_id does not exist.
            ValidationError: If agent not ACTIVE or no active key to rotate.
        """
        # 1. Generate new key
        new_key_id, full_key = self._key_gen.generate_api_key()

        # 2. Hash secret
        parts = self._key_gen.extract_key_parts(full_key)
        assert parts is not None, "Generated key should always be valid"
        _, secret = parts
        new_key_hash = self._key_gen.hash_secret(secret)

        # 3. Rotate on aggregate (records APIKeyRotated event)
        agent: Any = self._app.repository.get(cmd.agent_id)
        agent.request_rotate_api_key(new_key_id, new_key_hash)

        # 4. Persist
        self._app.save(agent)

        # Security: Log key_id (safe) but NEVER log full_key (secret)
        logger.info(
            "api_key_rotated",
            extra={
                "agent_id": str(cmd.agent_id),
                "new_key_id": new_key_id,
                "requested_by": cmd.requested_by,
            },
        )

        # 5. Return new key (display-once)
        return RotateAPIKeyResult(
            key_id=new_key_id,
            api_key=full_key,
        )
