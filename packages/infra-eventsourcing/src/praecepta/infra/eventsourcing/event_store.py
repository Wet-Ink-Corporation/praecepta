"""Event store factory for eventsourcing library configuration.

Provides a high-level wrapper around eventsourcing's InfrastructureFactory
with support for:
- Pydantic settings validation
- DATABASE_URL parsing for compatibility with other tools
- Environment-based configuration
- Connection pooling setup

Example:
    >>> from praecepta.infra.eventsourcing import get_event_store
    >>> factory = get_event_store()
    >>> recorder = factory.recorder
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from eventsourcing.postgres import Factory as PostgresInfrastructureFactory
from eventsourcing.utils import Environment
from praecepta.infra.eventsourcing.postgres_parser import (
    parse_database_url,
    parse_database_url_safe,
)
from praecepta.infra.eventsourcing.settings import EventSourcingSettings

if TYPE_CHECKING:
    from eventsourcing.persistence import ApplicationRecorder


class EventStoreFactory:
    """Factory for creating event store infrastructure.

    This factory wraps eventsourcing's InfrastructureFactory to provide:
    - Type-safe configuration via Pydantic settings
    - Automatic DATABASE_URL parsing to POSTGRES_* variables
    - Validation and sensible defaults
    - Connection pooling configuration

    Usage:
        # From environment variables
        factory = EventStoreFactory.from_env()
        recorder = factory.recorder

        # From explicit settings
        settings = EventSourcingSettings(
            postgres_dbname="mydb",
            postgres_user="user",
            postgres_password="password"
        )
        factory = EventStoreFactory(settings)

        # With DATABASE_URL parsing
        factory = EventStoreFactory.from_database_url(
            database_url="postgresql://user:pass@localhost:5432/mydb"
        )

    Attributes:
        _settings: The EventSourcingSettings instance.
        _infrastructure_factory: Lazily created eventsourcing factory.
    """

    def __init__(self, settings: EventSourcingSettings) -> None:
        """Initialize factory with validated settings.

        Args:
            settings: Validated EventSourcingSettings instance.
        """
        self._settings = settings
        self._infrastructure_factory: PostgresInfrastructureFactory | None = None

    @classmethod
    def from_env(cls) -> EventStoreFactory:
        """Create factory from environment variables.

        Attempts to parse DATABASE_URL if present, otherwise falls back to
        individual POSTGRES_* variables.

        Returns:
            Configured EventStoreFactory instance.

        Raises:
            pydantic.ValidationError: If required environment variables are
                missing or invalid.

        Examples:
            >>> import os
            >>> os.environ['POSTGRES_DBNAME'] = 'mydb'
            >>> os.environ['POSTGRES_USER'] = 'user'
            >>> os.environ['POSTGRES_PASSWORD'] = 'pass'
            >>> factory = EventStoreFactory.from_env()
        """
        # Check if DATABASE_URL is present
        database_url = os.getenv("DATABASE_URL")

        if database_url:
            # Parse DATABASE_URL and merge with any explicit POSTGRES_* overrides
            parsed = parse_database_url_safe(database_url)

            if parsed:
                # Create settings with DATABASE_URL values as defaults,
                # but allow explicit POSTGRES_* env vars to override
                settings = EventSourcingSettings(
                    postgres_dbname=os.getenv("POSTGRES_DBNAME", parsed["postgres_dbname"]),
                    postgres_host=os.getenv("POSTGRES_HOST", parsed["postgres_host"]),
                    postgres_port=int(os.getenv("POSTGRES_PORT", str(parsed["postgres_port"]))),
                    postgres_user=os.getenv("POSTGRES_USER", parsed["postgres_user"]),
                    postgres_password=os.getenv("POSTGRES_PASSWORD", parsed["postgres_password"]),
                )
                return cls(settings)

        # Fall back to individual POSTGRES_* variables
        settings = EventSourcingSettings()  # type: ignore[call-arg]
        return cls(settings)

    @classmethod
    def from_database_url(
        cls,
        database_url: str,
        **overrides: Any,
    ) -> EventStoreFactory:
        """Create factory from DATABASE_URL connection string.

        Args:
            database_url: PostgreSQL connection string (postgresql://...)
            **overrides: Optional overrides for other settings (pool_size, etc.)

        Returns:
            Configured EventStoreFactory instance.

        Raises:
            DatabaseURLParseError: If DATABASE_URL is invalid.
            pydantic.ValidationError: If settings are invalid after overrides.

        Examples:
            >>> factory = EventStoreFactory.from_database_url(
            ...     "postgresql://user:pass@localhost:5432/mydb",
            ...     postgres_pool_size=10
            ... )
        """
        parsed = parse_database_url(database_url)

        settings = EventSourcingSettings(
            **parsed,
            **overrides,
        )

        return cls(settings)

    @property
    def recorder(self) -> ApplicationRecorder:
        """Get the PostgresApplicationRecorder instance.

        Creates the recorder lazily on first access. The recorder provides:
        - Event storage with aggregate versioning (optimistic concurrency)
        - Notification log support via notification_id sequence
        - Automatic table creation if CREATE_TABLE=true

        Returns:
            PostgresApplicationRecorder configured with current settings.
        """
        if self._infrastructure_factory is None:
            self._infrastructure_factory = self._create_infrastructure_factory()

        return self._infrastructure_factory.application_recorder()

    def _create_infrastructure_factory(self) -> PostgresInfrastructureFactory:
        """Create eventsourcing InfrastructureFactory from settings.

        Returns:
            Configured PostgresInfrastructureFactory instance.
        """
        env_dict = self._settings.to_env_dict()

        # Wrap env dict in Environment object for Factory.construct()
        env = Environment(env=env_dict)

        # Use Factory.construct() which reads from environment
        factory = PostgresInfrastructureFactory.construct(env)

        return factory

    def close(self) -> None:
        """Close connection pool and release resources.

        Should be called when shutting down application to cleanly close
        database connections.
        """
        if self._infrastructure_factory is not None:
            # eventsourcing library handles cleanup internally
            self._infrastructure_factory.close()
            self._infrastructure_factory = None


# Global singleton factory (cached)
@lru_cache(maxsize=1)
def get_event_store() -> EventStoreFactory:
    """Get cached event store factory instance.

    This is the primary entry point for accessing the event store in
    application code. The factory is cached as a singleton.

    Returns:
        Singleton EventStoreFactory instance.

    Examples:
        >>> from praecepta.infra.eventsourcing import get_event_store
        >>> factory = get_event_store()
        >>> recorder = factory.recorder
    """
    return EventStoreFactory.from_env()
