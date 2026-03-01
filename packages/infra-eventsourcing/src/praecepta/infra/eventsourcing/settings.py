"""Eventsourcing library configuration using Pydantic settings.

This module provides type-safe configuration for the eventsourcing library
with PostgreSQL backend. Settings are loaded from environment variables
and validated using Pydantic.
"""

from __future__ import annotations

import os
import warnings

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EventSourcingSettings(BaseSettings):
    """Configuration for eventsourcing library with PostgreSQL.

    Environment Variables:
        PERSISTENCE_MODULE: Module path for persistence backend
            (default: eventsourcing.postgres)

        PostgreSQL Connection:
        POSTGRES_DBNAME: Database name (required)
        POSTGRES_HOST: PostgreSQL host (default: localhost)
        POSTGRES_PORT: PostgreSQL port (default: 5432)
        POSTGRES_USER: Database user (required)
        POSTGRES_PASSWORD: Database password (required, hidden in logs)

        Connection Pooling:
        POSTGRES_POOL_SIZE: Base pool size (default: 5)
        POSTGRES_MAX_OVERFLOW: Additional connections for bursts (default: 10)
        POSTGRES_CONN_MAX_AGE: Connection max age in seconds (default: 600)
        POSTGRES_CONNECT_TIMEOUT: Connection timeout in seconds (default: 30)
        POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT: Idle transaction timeout
            (default: 5)

        Table Management:
        CREATE_TABLE: Auto-create tables if not exist
            (default: true in dev, false in prod)
        POSTGRES_SCHEMA: PostgreSQL schema name (default: public)

        Locking:
        POSTGRES_LOCK_TIMEOUT: Table lock timeout in seconds (default: 5)

        Advanced:
        POSTGRES_PRE_PING: Validate connections before use (default: false)
        POSTGRES_SINGLE_ROW_TRACKING: Use single-row tracking (default: true)

    Example:
        >>> settings = EventSourcingSettings(
        ...     postgres_dbname='mydb',
        ...     postgres_user='user',
        ...     postgres_password='pass'
        ... )
        >>> env_dict = settings.to_env_dict()
        >>> env_dict['POSTGRES_DBNAME']
        'mydb'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Persistence backend
    persistence_module: str = "eventsourcing.postgres"

    # PostgreSQL connection (individual variables required by eventsourcing)
    postgres_dbname: str = Field(..., description="PostgreSQL database name")
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_user: str = Field(..., description="PostgreSQL user")
    postgres_password: str = Field(
        ...,
        repr=False,
        description="PostgreSQL password (hidden in logs)",
    )

    # Connection pooling
    postgres_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Base connection pool size (lazily created)",
    )
    postgres_max_overflow: int = Field(
        default=10,
        ge=0,
        le=100,
        description="Additional connections beyond pool size",
    )
    postgres_conn_max_age: int = Field(
        default=600,
        ge=60,
        description="Connection max age in seconds (10 minutes default)",
    )
    postgres_connect_timeout: int = Field(
        default=30,
        ge=5,
        description="Connection timeout in seconds",
    )
    postgres_idle_in_transaction_session_timeout: int = Field(
        default=5,
        ge=1,
        description="Idle transaction timeout in seconds",
    )

    # Table management
    create_table: bool = Field(
        default=True,
        description="Auto-create tables if not exist (dev: true, prod: false)",
    )
    postgres_schema: str = Field(
        default="public",
        description="PostgreSQL schema for event store tables",
    )

    # Locking
    postgres_lock_timeout: int = Field(
        default=5,
        ge=0,
        description="Table lock timeout in seconds (0 = no timeout)",
    )

    # Projection runner limits
    max_projection_runners: int = Field(
        default=8,
        ge=1,
        le=32,
        description="Maximum number of projection runners (caps discovered projections)",
    )

    # Projection-specific pool sizes (smaller than main pools since
    # projection upstream apps only read events and tracking recorders
    # only write position updates)
    postgres_projection_pool_size: int = Field(
        default=2,
        ge=1,
        le=20,
        description="Pool size for projection upstream apps and tracking recorders",
    )
    postgres_projection_max_overflow: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Max overflow for projection pools",
    )

    # Advanced options
    postgres_pre_ping: bool = Field(
        default=False,
        description="Validate connections before use (adds latency)",
    )
    postgres_single_row_tracking: bool = Field(
        default=True,
        description="Use single-row tracking for process applications",
    )

    @field_validator("postgres_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate PostgreSQL port is in valid range."""
        if not 1 <= v <= 65535:
            msg = "postgres_port must be between 1 and 65535"
            raise ValueError(msg)
        return v

    @field_validator("create_table")
    @classmethod
    def validate_create_table_for_production(cls, v: bool) -> bool:
        """Warn if CREATE_TABLE=true in production environment.

        In production, tables should be created via migrations
        for better control and versioning.
        """
        environment = os.getenv("ENVIRONMENT", "development")

        if environment == "production" and v:
            warnings.warn(
                "CREATE_TABLE=true in production environment. Consider using migrations instead.",
                UserWarning,
                stacklevel=2,
            )

        return v

    def to_env_dict(self) -> dict[str, str]:
        """Convert settings to environment variable dictionary.

        Returns:
            Dictionary with uppercase keys suitable for
            InfrastructureFactory.construct(env).

        Example:
            >>> settings = EventSourcingSettings(
            ...     postgres_dbname='db',
            ...     postgres_user='user',
            ...     postgres_password='pass'
            ... )
            >>> env = settings.to_env_dict()
            >>> env['PERSISTENCE_MODULE']
            'eventsourcing.postgres'
        """
        return {
            "PERSISTENCE_MODULE": self.persistence_module,
            "POSTGRES_DBNAME": self.postgres_dbname,
            "POSTGRES_HOST": self.postgres_host,
            "POSTGRES_PORT": str(self.postgres_port),
            "POSTGRES_USER": self.postgres_user,
            "POSTGRES_PASSWORD": self.postgres_password,
            "POSTGRES_POOL_SIZE": str(self.postgres_pool_size),
            "POSTGRES_MAX_OVERFLOW": str(self.postgres_max_overflow),
            "POSTGRES_CONN_MAX_AGE": str(self.postgres_conn_max_age),
            "POSTGRES_CONNECT_TIMEOUT": str(self.postgres_connect_timeout),
            "POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT": str(
                self.postgres_idle_in_transaction_session_timeout
            ),
            "CREATE_TABLE": str(self.create_table).lower(),
            "POSTGRES_SCHEMA": self.postgres_schema,
            "POSTGRES_LOCK_TIMEOUT": str(self.postgres_lock_timeout),
            "POSTGRES_PRE_PING": "y" if self.postgres_pre_ping else "",
            "POSTGRES_SINGLE_ROW_TRACKING": "y" if self.postgres_single_row_tracking else "",
        }
