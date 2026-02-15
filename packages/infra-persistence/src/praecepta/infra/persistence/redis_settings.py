"""Redis configuration using Pydantic settings.

This module provides type-safe configuration for Redis connection
with async client support. Settings are loaded from environment variables
and validated using Pydantic.
"""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisSettings(BaseSettings):
    """Configuration for Redis connection.

    Environment Variables:
        REDIS_URL: Full connection URL (redis://host:port/db)
            Takes precedence over individual variables if set.

        Individual Connection Variables:
        REDIS_HOST: Redis host (default: localhost)
        REDIS_PORT: Redis port (default: 6379)
        REDIS_DB: Database number (default: 0)
        REDIS_PASSWORD: Optional password (hidden in logs)

        Connection Pooling:
        REDIS_POOL_SIZE: Maximum connections in pool (default: 10)
        REDIS_SOCKET_TIMEOUT: Socket timeout in seconds (default: 5.0)
        REDIS_SOCKET_CONNECT_TIMEOUT: Connection timeout in seconds (default: 5.0)

    Example:
        >>> settings = RedisSettings(redis_host='localhost', redis_port=6379)
        >>> url = settings.get_url()
        >>> url
        'redis://localhost:6379/0'

        >>> settings = RedisSettings.from_url('redis://myhost:6380/1')
        >>> settings.redis_host
        'myhost'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Full URL (optional, takes precedence)
    redis_url: str | None = Field(
        default=None,
        description="Full Redis URL (redis://host:port/db)",
    )

    # Individual connection settings
    redis_host: str = Field(
        default="localhost",
        description="Redis host",
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port",
    )
    redis_db: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis database number (0-15)",
    )
    redis_password: str | None = Field(
        default=None,
        repr=False,
        description="Redis password (hidden in logs)",
    )

    # Connection pooling
    redis_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum connections in pool",
    )
    redis_socket_timeout: float = Field(
        default=5.0,
        ge=0.1,
        description="Socket timeout in seconds",
    )
    redis_socket_connect_timeout: float = Field(
        default=5.0,
        ge=0.1,
        description="Connection timeout in seconds",
    )

    @field_validator("redis_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate Redis port is in valid range."""
        if not 1 <= v <= 65535:
            msg = "redis_port must be between 1 and 65535"
            raise ValueError(msg)
        return v

    @classmethod
    def from_url(cls, url: str) -> RedisSettings:
        """Create settings from a Redis URL.

        Args:
            url: Redis connection URL (redis://[password@]host:port/db)

        Returns:
            RedisSettings instance with parsed values.

        Raises:
            ValueError: If URL is invalid or scheme is not redis/rediss.

        Example:
            >>> settings = RedisSettings.from_url('redis://localhost:6379/0')
            >>> settings.redis_host
            'localhost'
        """
        parsed = urlparse(url)

        if parsed.scheme not in ("redis", "rediss"):
            msg = f"Invalid Redis URL scheme: {parsed.scheme}"
            raise ValueError(msg)

        # Extract components
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        password = parsed.password
        db = 0

        # Parse database from path
        if parsed.path and parsed.path != "/":
            try:
                db = int(parsed.path.lstrip("/"))
            except ValueError:
                msg = f"Invalid database number in URL path: {parsed.path}"
                raise ValueError(msg) from None

        return cls(
            redis_url=url,
            redis_host=host,
            redis_port=port,
            redis_db=db,
            redis_password=password,
        )

    def get_url(self) -> str:
        """Build Redis URL from settings.

        If redis_url is set, returns it directly. Otherwise builds
        URL from individual settings.

        Returns:
            Redis connection URL string.

        Example:
            >>> settings = RedisSettings(redis_host='myhost', redis_port=6380)
            >>> settings.get_url()
            'redis://myhost:6380/0'
        """
        if self.redis_url:
            return self.redis_url

        # Build URL from components
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
