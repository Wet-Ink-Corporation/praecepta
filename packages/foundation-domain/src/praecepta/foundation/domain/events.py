"""Base event classes for domain event sourcing.

This module provides the foundational event classes that all domain events
inherit from. It extends the eventsourcing library's DomainEvent
with multi-tenancy support, distributed tracing, and standardized serialization.

Example:
    Define a domain event by subclassing BaseEvent::

        from dataclasses import dataclass
        from praecepta.foundation.domain.events import BaseEvent

        @dataclass(frozen=True)
        class ResourceCreated(BaseEvent):
            title: str
            scope_type: str

        # Event topic for routing:
        ResourceCreated.get_topic()
        # Returns: "myapp.domain.events:ResourceCreated"

Event Schema Evolution Strategy:
    Events are immutable once persisted. Schema changes must be handled
    carefully to maintain replay compatibility.

    **Backward-compatible changes** (safe without upcaster):
    - Adding optional fields with defaults (e.g., ``category: str = ""``)
    - The ``@event`` decorator stores all kwargs; missing fields in old
      events are filled with defaults during replay

    **Breaking changes** (require transcoder upcaster):
    - Renaming fields
    - Changing field types
    - Removing fields
    - Adding required fields without defaults

    The eventsourcing library supports custom transcoders for upcasting
    old event schemas. Register upcasters via the application's
    ``env["TRANSCODER_TOPIC"]`` configuration. Example pattern::

        # In transcoder registration:
        def upcast_suspended_v1_to_v2(data: dict) -> dict:
            if "category" not in data:
                data["category"] = ""  # default for old events
            return data

    For aggregate events created by the ``@event`` decorator (e.g.,
    ``Tenant.Suspended``), event classes are dynamically generated inner
    classes. Their schema is defined by the kwargs of the decorated
    method. Adding optional parameters with defaults to ``_apply_*``
    methods is the safest evolution strategy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

from eventsourcing.domain import DomainEvent


@dataclass(frozen=True, kw_only=True)
class BaseEvent(DomainEvent):
    """Base class for all domain events.

    Extends eventsourcing.domain.DomainEvent with cross-cutting concerns:

    - Multi-tenancy via required tenant_id field
    - Distributed tracing via correlation_id and causation_id
    - Audit trail via user_id
    - Strict tenant_id format validation

    All domain events MUST inherit from this class to ensure
    consistent metadata, validation, and serialization behavior.

    Attributes:
        tenant_id: Organizational boundary identifier (required). Must be a
            lowercase alphanumeric slug with optional hyphens, 2-63 characters.
            Examples: "acme-corp", "contoso", "big-bank-nyc"
        correlation_id: Request or workflow ID for distributed tracing.
            Links all events triggered by a single user request.
        causation_id: Parent event ID that triggered this event.
            Forms a causal chain between events.
        user_id: Acting user identifier for audit trail.
            Records who initiated the action that produced this event.

    Inherited from DomainEvent (eventsourcing library):
        originator_id: Aggregate ID (UUID) that emitted this event.
        originator_version: Aggregate version for optimistic concurrency control.
        timestamp: Event occurrence time (datetime with timezone, UTC).

    Example:
        Creating a concrete domain event::

            @dataclass(frozen=True)
            class ResourceCreated(BaseEvent):
                title: str
                owner_id: UUID

            event = ResourceCreated(
                originator_id=uuid4(),
                originator_version=1,
                timestamp=datetime.now(timezone.utc),
                tenant_id="acme-corp",
                correlation_id="req-abc123",
                title="Q1 Planning",
                owner_id=uuid4(),
            )

    Note:
        Events are immutable (frozen dataclass). Attempting to modify any
        field after instantiation will raise a FrozenInstanceError.
    """

    # Required multi-tenancy field
    tenant_id: str

    # Optional observability fields
    correlation_id: str | None = None
    causation_id: str | None = None
    user_id: str | None = None

    # Validation pattern for tenant_id (class-level constant)
    # Pattern: lowercase alphanumeric, can contain hyphens but not at start/end
    _TENANT_ID_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")

    def __post_init__(self) -> None:
        """Validate fields after dataclass initialization.

        Validates tenant_id format. Called automatically by dataclass
        after __init__ completes.

        Raises:
            ValueError: If tenant_id doesn't match format or length requirements.
        """
        self._validate_tenant_id(self.tenant_id)

    @classmethod
    def _validate_tenant_id(cls, value: str) -> str:
        """Validate tenant_id follows lowercase slug format.

        Format rules:
        - Lowercase alphanumeric characters and hyphens only
        - Must start and end with alphanumeric character (no leading/trailing hyphens)
        - Length: 2-63 characters (DNS label compatible)

        Args:
            value: The tenant_id value to validate.

        Returns:
            The validated tenant_id value (unchanged if valid).

        Raises:
            ValueError: If tenant_id doesn't match format or length requirements.

        Examples:
            Valid tenant IDs::

                "acme-corp"      # Lowercase with hyphens
                "contoso"        # No hyphens
                "big-bank-nyc"   # Multiple hyphens
                "a1"             # Minimum length (2 chars)

            Invalid tenant IDs::

                "Acme"           # Uppercase letters
                "acme_corp"      # Underscore not allowed
                "a"              # Too short (< 2 chars)
                "-acme"          # Leading hyphen
                "acme-"          # Trailing hyphen
        """
        # Length validation
        if len(value) < 2:
            msg = f"Invalid tenant_id '{value}': length must be 2-63 characters (got {len(value)})"
            raise ValueError(msg)
        if len(value) > 63:
            msg = f"Invalid tenant_id '{value}': length must be 2-63 characters (got {len(value)})"
            raise ValueError(msg)

        # Pattern validation
        if not cls._TENANT_ID_PATTERN.match(value):
            msg = (
                f"Invalid tenant_id '{value}': must be lowercase alphanumeric "
                f"with hyphens, starting and ending with alphanumeric"
            )
            raise ValueError(msg)

        return value

    @classmethod
    def get_topic(cls) -> str:
        """Get fully-qualified topic for event routing.

        Returns the event topic in format: "{module_path}:{class_name}"

        The topic is used by the eventsourcing library for:
        - Event deserialization (topic resolves to Python class)
        - Projection filtering (subscribe to topic patterns)
        - Event routing and notification logs

        Returns:
            Fully-qualified topic string in format "module:class".

        Example:
            For a class defined in myapp.domain.events::

                class ResourceCreated(BaseEvent):
                    ...

                ResourceCreated.get_topic()
                # Returns: "myapp.domain.events:ResourceCreated"
        """
        return f"{cls.__module__}:{cls.__qualname__}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize event to dictionary.

        Converts the event to a dictionary suitable for JSON serialization.
        UUID fields are converted to standard hex format with hyphens.
        Datetime fields are converted to ISO 8601 strings with UTC timezone.

        Returns:
            Dictionary containing all base event fields. Subclass fields
            are NOT included; subclasses should override this method
            if custom field serialization is needed.

        Note:
            This method serializes only the base event fields defined in
            BaseEvent. Subclass-specific fields must be handled by overriding
            this method in the subclass.

        Example:
            ::

                event = ResourceCreated(
                    originator_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                    originator_version=3,
                    timestamp=datetime(2026, 1, 24, 10, 30, tzinfo=timezone.utc),
                    tenant_id="acme-corp",
                    correlation_id="req-123",
                    title="Test",
                )

                event.to_dict()
                # Returns:
                # {
                #     "originator_id": "550e8400-...",
                #     "originator_version": 3,
                #     "timestamp": "2026-01-24T10:30:00+00:00",
                #     "tenant_id": "acme-corp",
                #     "correlation_id": "req-123",
                #     "causation_id": None,
                #     "user_id": None,
                # }
        """
        # Get originator_id - handle both UUID and string cases
        originator_id = self.originator_id
        originator_id_str = str(originator_id) if originator_id is not None else None

        # Get timestamp - handle datetime serialization
        timestamp = self.timestamp
        timestamp_str: str | None = None
        if timestamp is not None:
            timestamp_str = timestamp.isoformat()

        return {
            "originator_id": originator_id_str,
            "originator_version": self.originator_version,
            "timestamp": timestamp_str,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
        }
