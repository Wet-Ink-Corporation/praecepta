"""Event-sourced Agent aggregate with lifecycle state machine.

State machine:
    (creation) -> ACTIVE
    ACTIVE <-> SUSPENDED (via request_suspend, request_reactivate)
"""

from __future__ import annotations

from datetime import UTC, datetime

from eventsourcing.domain import event

from praecepta.foundation.domain.agent_value_objects import AgentStatus, AgentTypeId
from praecepta.foundation.domain.aggregates import BaseAggregate
from praecepta.foundation.domain.exceptions import (
    InvalidStateTransitionError,
    ValidationError,
)
from praecepta.foundation.domain.user_value_objects import DisplayName


class Agent(BaseAggregate):
    """Event-sourced Agent aggregate with lifecycle state machine.

    Attributes:
        agent_type_id: Validated agent type identifier (immutable).
        tenant_id: Tenant boundary (immutable, from BaseAggregate).
        display_name: Human-readable agent name.
        status: Current lifecycle state (AgentStatus enum value).
        active_keys: List of active API key metadata (populated on key issuance).
        revoked_keys: List of revoked key_id strings (audit trail).
    """

    # -- Creation (records Agent.Registered event) --

    @event("Registered")
    def __init__(
        self,
        *,
        agent_type_id: str,
        tenant_id: str,
        display_name: str,
    ) -> None:
        """Create a new Agent in ACTIVE state.

        Args:
            agent_type_id: Validated agent type identifier.
            tenant_id: Tenant slug.
            display_name: Human-readable agent name.

        Raises:
            ValueError: If agent_type_id or display_name fails validation.
        """
        validated_type_id = AgentTypeId(agent_type_id)
        validated_name = DisplayName(display_name)

        self.agent_type_id: str = validated_type_id.value
        self.tenant_id: str = tenant_id
        self.display_name: str = validated_name.value
        self.status: str = AgentStatus.ACTIVE.value
        self.active_keys: list[dict[str, str]] = []
        self.revoked_keys: list[str] = []

    # -- Public command methods --

    def request_suspend(self, reason: str | None = None) -> None:
        """Suspend an active agent. ACTIVE -> SUSPENDED.

        Idempotent: calling on an already-SUSPENDED agent is a no-op.

        Args:
            reason: Optional human-readable suspension reason.

        Raises:
            InvalidStateTransitionError: If current state is not ACTIVE
                (and not already SUSPENDED for idempotency).
        """
        if self.status == AgentStatus.SUSPENDED.value:
            return  # idempotent
        if self.status != AgentStatus.ACTIVE.value:
            raise InvalidStateTransitionError(
                f"Cannot suspend agent {self.id}: current state is {self.status}, expected ACTIVE"
            )
        self._apply_suspend(reason=reason or "")

    def request_reactivate(self) -> None:
        """Reactivate a suspended agent. SUSPENDED -> ACTIVE.

        Idempotent: calling on an already-ACTIVE agent is a no-op.

        Raises:
            InvalidStateTransitionError: If current state is not SUSPENDED
                (and not already ACTIVE for idempotency).
        """
        if self.status == AgentStatus.ACTIVE.value:
            return  # idempotent
        if self.status != AgentStatus.SUSPENDED.value:
            raise InvalidStateTransitionError(
                f"Cannot reactivate agent {self.id}: "
                f"current state is {self.status}, expected SUSPENDED"
            )
        self._apply_reactivate()

    def request_issue_api_key(
        self,
        key_id: str,
        key_hash: str,
        created_at: str,
    ) -> None:
        """Issue new API key for agent.

        Args:
            key_id: 8-char identifier (stored unhashed for lookup).
            key_hash: bcrypt hash of secret portion (NEVER plaintext).
            created_at: ISO 8601 timestamp string.

        Raises:
            ValidationError: If agent is not ACTIVE.
        """
        if self.status != AgentStatus.ACTIVE.value:
            raise ValidationError(
                "agent_status",
                f"Cannot issue key for {self.status} agent",
            )
        self._apply_api_key_issued(key_id=key_id, key_hash=key_hash, created_at=created_at)

    def request_rotate_api_key(self, new_key_id: str, new_key_hash: str) -> None:
        """Rotate API key atomically: revoke current, issue new.

        Args:
            new_key_id: 8-char identifier for new key.
            new_key_hash: bcrypt hash for new key secret.

        Raises:
            ValidationError: If no active key to rotate or agent not ACTIVE.
        """
        if self.status != AgentStatus.ACTIVE.value:
            raise ValidationError(
                "agent_status",
                "Cannot rotate key for non-active agent",
            )
        active = [k for k in self.active_keys if k["status"] == "active"]
        if not active:
            raise ValidationError(
                "active_keys",
                "No active key to rotate",
            )
        old_key_id = active[0]["key_id"]
        self._apply_api_key_rotated(
            new_key_id=new_key_id,
            new_key_hash=new_key_hash,
            revoked_key_id=old_key_id,
        )

    # -- Private @event mutators --

    @event("Suspended")
    def _apply_suspend(self, reason: str) -> None:
        self.status = AgentStatus.SUSPENDED.value

    @event("Reactivated")
    def _apply_reactivate(self) -> None:
        self.status = AgentStatus.ACTIVE.value

    @event("APIKeyIssued")
    def _apply_api_key_issued(self, key_id: str, key_hash: str, created_at: str) -> None:
        self.active_keys.append(
            {
                "key_id": key_id,
                "key_hash": key_hash,
                "created_at": created_at,
                "status": "active",
            }
        )

    @event("APIKeyRotated")
    def _apply_api_key_rotated(
        self,
        new_key_id: str,
        new_key_hash: str,
        revoked_key_id: str,
    ) -> None:
        # Mark old key as revoked
        self.active_keys = [
            {**k, "status": "revoked"} if k["key_id"] == revoked_key_id else k
            for k in self.active_keys
        ]
        self.revoked_keys.append(revoked_key_id)

        # Add new key
        self.active_keys.append(
            {
                "key_id": new_key_id,
                "key_hash": new_key_hash,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "active",
            }
        )
