"""Tests for Redis client factory and connection management."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from praecepta.infra.persistence.redis_client import RedisFactory, get_redis_factory
from praecepta.infra.persistence.redis_settings import RedisSettings


@pytest.mark.unit
class TestRedisFactory:
    def test_from_env_with_redis_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REDIS_URL", "redis://myhost:6380/2")
        factory = RedisFactory.from_env()
        assert factory.settings.redis_host == "myhost"
        assert factory.settings.redis_port == 6380
        assert factory.settings.redis_db == 2

    def test_from_env_without_redis_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("REDIS_URL", raising=False)
        factory = RedisFactory.from_env()
        assert factory.settings.redis_host == "localhost"

    def test_from_url(self) -> None:
        factory = RedisFactory.from_url("redis://testhost:6381/3")
        assert factory.settings.redis_host == "testhost"
        assert factory.settings.redis_port == 6381
        assert factory.settings.redis_db == 3

    def test_settings_property(self) -> None:
        settings = RedisSettings(redis_host="myhost")
        factory = RedisFactory(settings)
        assert factory.settings is settings

    @pytest.mark.asyncio(loop_scope="function")
    async def test_get_client_creates_lazily(self) -> None:
        settings = RedisSettings()
        factory = RedisFactory(settings)

        mock_pool = MagicMock()
        mock_client = MagicMock()

        with (
            patch("redis.asyncio.ConnectionPool") as mock_pool_cls,
            patch("redis.asyncio.Redis") as mock_redis_cls,
        ):
            mock_pool_cls.from_url.return_value = mock_pool
            mock_redis_cls.return_value = mock_client

            client = await factory.get_client()
            assert client is mock_client

            # Second call returns same client
            client2 = await factory.get_client()
            assert client2 is mock_client
            mock_pool_cls.from_url.assert_called_once()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_close_cleans_up_client_and_pool(self) -> None:
        settings = RedisSettings()
        factory = RedisFactory(settings)

        mock_pool = AsyncMock()
        mock_client = AsyncMock()

        with (
            patch("redis.asyncio.ConnectionPool") as mock_pool_cls,
            patch("redis.asyncio.Redis") as mock_redis_cls,
        ):
            mock_pool_cls.from_url.return_value = mock_pool
            mock_redis_cls.return_value = mock_client

            await factory.get_client()
            await factory.close()

            mock_client.aclose.assert_awaited_once()
            mock_pool.aclose.assert_awaited_once()
            assert factory._client is None
            assert factory._pool is None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_close_noop_when_not_connected(self) -> None:
        settings = RedisSettings()
        factory = RedisFactory(settings)
        # Should not raise
        await factory.close()


@pytest.mark.unit
class TestGetRedisFactory:
    def test_returns_cached_singleton(self) -> None:
        get_redis_factory.cache_clear()
        try:
            f1 = get_redis_factory()
            f2 = get_redis_factory()
            assert f1 is f2
        finally:
            get_redis_factory.cache_clear()
