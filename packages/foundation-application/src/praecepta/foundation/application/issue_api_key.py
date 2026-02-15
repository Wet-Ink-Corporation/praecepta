"""Command and handler for issuing API keys."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
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
class IssueAPIKeyCommand:
    """Command to issue a new API key for an agent."""

    agent_id: UUID
    requested_by: str  # Principal subject


class IssueAPIKeyHandler:
    """Issues API key: generates, hashes, stores hash in aggregate, returns plaintext.

    Security invariant: Plaintext key exists ONLY in handler memory and
    the return value. It is NEVER logged, persisted, or stored in events.
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

    def handle(self, cmd: IssueAPIKeyCommand) -> tuple[str, str]:
        """Issue new API key for agent.

        Returns:
            (key_id, full_plaintext_key) -- display-once.

        Raises:
            AggregateNotFoundError: If agent_id does not exist.
            ValidationError: If agent is not ACTIVE.
        """
        # 1. Generate key (application layer, NOT domain)
        key_id, full_key = self._key_gen.generate_api_key()

        # 2. Extract and hash secret
        parts = self._key_gen.extract_key_parts(full_key)
        assert parts is not None, "Generated key should always be valid"
        _, secret = parts
        key_hash = self._key_gen.hash_secret(secret)

        # 3. Store hash in aggregate (records APIKeyIssued event)
        agent: Any = self._app.repository.get(cmd.agent_id)
        created_at = datetime.now(UTC).isoformat()
        agent.request_issue_api_key(key_id, key_hash, created_at)

        # 4. Persist
        self._app.save(agent)

        # Security: Log key_id (safe) but NEVER log full_key (secret)
        logger.info(
            "api_key_issued",
            extra={
                "agent_id": str(cmd.agent_id),
                "key_id": key_id,  # Safe to log (acts as identifier)
                "requested_by": cmd.requested_by,
            },
        )

        # 5. Return plaintext key (ONLY TIME it exists)
        return key_id, full_key
