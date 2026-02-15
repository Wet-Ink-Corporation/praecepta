"""Redis client factory for async connection management.

This module provides a factory for creating and managing Redis async clients
with connection pooling support.

Example:
    >>> from praecepta.infra.persistence.redis_client import get_redis_factory
    >>> factory = get_redis_factory()
    >>> client = await factory.get_client()
    >>> await client.ping()
    True
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from praecepta.infra.persistence.redis_settings import RedisSettings


class RedisFactory:
    """Factory for creating Redis async clients.

    This factory wraps redis-py's async client to provide:
    - Type-safe configuration via Pydantic settings
    - Automatic REDIS_URL parsing
    - Connection pooling configuration
    - Graceful shutdown support

    Usage:
        # From environment variables
        factory = RedisFactory.from_env()
        client = await factory.get_client()
        await client.ping()
        await factory.close()

        # From explicit settings
        settings = RedisSettings(redis_host="localhost", redis_port=6379)
        factory = RedisFactory(settings)

        # From URL
        factory = RedisFactory.from_url("redis://localhost:6379/0")

    Attributes:
        _settings: The RedisSettings instance.
        _client: Lazily created Redis client instance.
    """

    def __init__(self, settings: RedisSettings) -> None:
        """Initialize factory with validated settings.

        Args:
            settings: Validated RedisSettings instance.
        """
        self._settings = settings
        self._client: Any = None

    @classmethod
    def from_env(cls) -> RedisFactory:
        """Create factory from environment variables.

        Attempts to parse REDIS_URL if present, otherwise falls back to
        individual REDIS_* variables.

        Returns:
            Configured RedisFactory instance.

        Raises:
            pydantic.ValidationError: If settings are invalid.

        Example:
            >>> import os
            >>> os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
            >>> factory = RedisFactory.from_env()
        """
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            return cls.from_url(redis_url)

        # Fall back to individual variables
        settings = RedisSettings()
        return cls(settings)

    @classmethod
    def from_url(cls, url: str) -> RedisFactory:
        """Create factory from Redis URL.

        Args:
            url: Redis connection URL (redis://[password@]host:port/db)

        Returns:
            Configured RedisFactory instance.

        Raises:
            ValueError: If URL is invalid.

        Example:
            >>> factory = RedisFactory.from_url("redis://localhost:6379/0")
        """
        settings = RedisSettings.from_url(url)
        return cls(settings)

    @property
    def settings(self) -> RedisSettings:
        """Get the Redis settings."""
        return self._settings

    async def get_client(self) -> Any:
        """Get the Redis async client.

        Creates the client lazily on first access. The client uses
        connection pooling configured via settings.

        Returns:
            Async Redis client configured with current settings.
        """
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        """Create Redis async client from settings.

        Returns:
            Configured async Redis client.
        """
        import redis.asyncio as aioredis

        client: Any = aioredis.from_url(  # type: ignore[no-untyped-call]
            self._settings.get_url(),
            max_connections=self._settings.redis_pool_size,
            socket_timeout=self._settings.redis_socket_timeout,
            socket_connect_timeout=self._settings.redis_socket_connect_timeout,
            decode_responses=False,
        )
        return client

    async def close(self) -> None:
        """Close the Redis client and release resources.

        Should be called when shutting down application to cleanly close
        connections.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None


@lru_cache(maxsize=1)
def get_redis_factory() -> RedisFactory:
    """Get cached Redis factory singleton.

    This is the primary entry point for accessing Redis in application code.
    The factory is cached as a singleton.

    Returns:
        Singleton RedisFactory instance.

    Example:
        >>> from praecepta.infra.persistence.redis_client import get_redis_factory
        >>> factory = get_redis_factory()
        >>> client = await factory.get_client()
    """
    return RedisFactory.from_env()
