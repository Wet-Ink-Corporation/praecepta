"""Integration tests for RedisFactory against real Redis.

Verifies connection establishment and cleanup with a real Redis container.
"""

from __future__ import annotations

import pytest

from praecepta.infra.persistence.redis_client import RedisFactory


@pytest.mark.integration
class TestRedisFactoryLive:
    """RedisFactory tests against a real Redis container."""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_get_client_connects(self, redis_url):
        """Client should successfully connect and respond to PING."""
        factory = RedisFactory.from_url(redis_url)
        client = await factory.get_client()

        result = await client.ping()
        assert result is True

        await factory.close()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_close_cleans_up_cleanly(self, redis_url):
        """close() should not raise and should clear internal state."""
        factory = RedisFactory.from_url(redis_url)
        _ = await factory.get_client()

        await factory.close()
        # After close, internal client should be None
        assert factory._client is None
        assert factory._pool is None
