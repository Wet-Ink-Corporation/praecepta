"""Tests for HybridConfigCache."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from praecepta.infra.eventsourcing.config_cache import HybridConfigCache


@pytest.mark.unit
class TestHybridConfigCacheL1:
    """Tests for L1 (in-memory) cache behavior."""

    @pytest.mark.asyncio
    async def test_get_returns_none_on_miss(self) -> None:
        cache = HybridConfigCache()
        result = await cache.get("tenant1", "key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        cache = HybridConfigCache()
        value = {"enabled": True, "threshold": 0.5}
        await cache.set("tenant1", "key1", value)
        result = await cache.get("tenant1", "key1")
        assert result == value

    @pytest.mark.asyncio
    async def test_tenant_isolation(self) -> None:
        cache = HybridConfigCache()
        value_a = {"value": "a"}
        value_b = {"value": "b"}

        await cache.set("tenant_a", "key1", value_a)
        await cache.set("tenant_b", "key1", value_b)

        assert await cache.get("tenant_a", "key1") == value_a
        assert await cache.get("tenant_b", "key1") == value_b

    @pytest.mark.asyncio
    async def test_invalidate_removes_entry(self) -> None:
        cache = HybridConfigCache()
        await cache.set("tenant1", "key1", {"value": "test"})

        await cache.invalidate("tenant1", "key1")

        result = await cache.get("tenant1", "key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_key(self) -> None:
        cache = HybridConfigCache()
        # Should not raise
        await cache.invalidate("tenant1", "nonexistent")

    @pytest.mark.asyncio
    async def test_invalidate_tenant_removes_all_keys(self) -> None:
        cache = HybridConfigCache()
        await cache.set("tenant1", "key1", {"value": "1"})
        await cache.set("tenant1", "key2", {"value": "2"})
        await cache.set("tenant1", "key3", {"value": "3"})
        await cache.set("tenant2", "key1", {"value": "other"})

        await cache.invalidate_tenant("tenant1")

        assert await cache.get("tenant1", "key1") is None
        assert await cache.get("tenant1", "key2") is None
        assert await cache.get("tenant1", "key3") is None
        # Other tenant should be unaffected
        assert await cache.get("tenant2", "key1") == {"value": "other"}

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self) -> None:
        cache = HybridConfigCache()
        await cache.set("tenant1", "key1", {"value": "old"})
        await cache.set("tenant1", "key1", {"value": "new"})

        result = await cache.get("tenant1", "key1")
        assert result == {"value": "new"}

    def test_cache_key_format(self) -> None:
        cache = HybridConfigCache()
        key = cache._cache_key("my-tenant", "my-key")
        assert key == "tenant:my-tenant:config:my-key"


@pytest.mark.unit
class TestHybridConfigCacheL2:
    """Tests for L2 (Redis) cache behavior with mocked Redis."""

    @pytest.mark.asyncio
    async def test_set_writes_to_l2(self) -> None:
        mock_redis = AsyncMock()
        cache = HybridConfigCache(redis_client=mock_redis)

        value = {"enabled": True}
        await cache.set("tenant1", "key1", value)

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "tenant:tenant1:config:key1"

    @pytest.mark.asyncio
    async def test_l2_fallback_on_l1_miss(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"enabled": true}'
        cache = HybridConfigCache(redis_client=mock_redis)

        result = await cache.get("tenant1", "key1")

        assert result == {"enabled": True}
        mock_redis.get.assert_called_once_with("tenant:tenant1:config:key1")

    @pytest.mark.asyncio
    async def test_l2_hit_promotes_to_l1(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"enabled": true}'
        cache = HybridConfigCache(redis_client=mock_redis)

        # First call: L2 hit
        result1 = await cache.get("tenant1", "key1")
        assert result1 == {"enabled": True}

        # Second call: should be L1 hit (no additional L2 call)
        result2 = await cache.get("tenant1", "key1")
        assert result2 == {"enabled": True}
        assert mock_redis.get.call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_invalidate_deletes_from_l2(self) -> None:
        mock_redis = AsyncMock()
        cache = HybridConfigCache(redis_client=mock_redis)

        await cache.set("tenant1", "key1", {"value": "test"})
        await cache.invalidate("tenant1", "key1")

        mock_redis.delete.assert_called_once_with("tenant:tenant1:config:key1")

    @pytest.mark.asyncio
    async def test_invalidate_tenant_scans_l2(self) -> None:
        mock_redis = AsyncMock()
        # Simulate SCAN returning keys then exhausting cursor
        mock_redis.scan.return_value = (
            0,
            [b"tenant:tenant1:config:key1", b"tenant:tenant1:config:key2"],
        )
        cache = HybridConfigCache(redis_client=mock_redis)

        await cache.invalidate_tenant("tenant1")

        mock_redis.scan.assert_called_once()
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_l2_miss_returns_none(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        cache = HybridConfigCache(redis_client=mock_redis)

        result = await cache.get("tenant1", "key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_redis_disables_l2(self) -> None:
        cache = HybridConfigCache(redis_client=None)

        # Should work with L1 only
        await cache.set("tenant1", "key1", {"value": "test"})
        result = await cache.get("tenant1", "key1")
        assert result == {"value": "test"}

        await cache.invalidate("tenant1", "key1")
        assert await cache.get("tenant1", "key1") is None
