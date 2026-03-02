"""Integration tests for HybridConfigCache against real Redis.

Verifies L1/L2 cache behavior, promotion, invalidation, and TTL expiry.
"""

from __future__ import annotations

import asyncio

import pytest

from praecepta.infra.eventsourcing.config_cache import HybridConfigCache


@pytest.mark.integration
class TestHybridConfigCacheRedis:
    """HybridConfigCache tests against a real Redis container."""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_set_and_get_round_trip(self, redis_client):
        cache = HybridConfigCache(redis_client=redis_client)

        await cache.set("tenant-a", "features", {"dark_mode": True})
        result = await cache.get("tenant-a", "features")

        assert result == {"dark_mode": True}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_l2_fallback_on_l1_miss(self, redis_client):
        """Clear L1, verify L2 serves the value and promotes back to L1."""
        cache = HybridConfigCache(redis_client=redis_client)

        await cache.set("tenant-b", "config-key", {"value": 42})

        # Clear L1 manually
        cache._l1.clear()

        # Should fetch from L2 (Redis) and promote to L1
        result = await cache.get("tenant-b", "config-key")
        assert result == {"value": 42}

        # Verify L1 was repopulated
        l1_key = cache._cache_key("tenant-b", "config-key")
        assert l1_key in cache._l1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_invalidate_removes_from_both_levels(self, redis_client):
        cache = HybridConfigCache(redis_client=redis_client)

        await cache.set("tenant-c", "key1", {"x": 1})
        await cache.invalidate("tenant-c", "key1")

        assert await cache.get("tenant-c", "key1") is None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_invalidate_tenant_removes_all_keys(self, redis_client):
        cache = HybridConfigCache(redis_client=redis_client)

        await cache.set("tenant-d", "key1", {"a": 1})
        await cache.set("tenant-d", "key2", {"b": 2})
        await cache.set("other-tenant", "key1", {"c": 3})

        await cache.invalidate_tenant("tenant-d")

        assert await cache.get("tenant-d", "key1") is None
        assert await cache.get("tenant-d", "key2") is None
        # Other tenant should be unaffected
        assert await cache.get("other-tenant", "key1") == {"c": 3}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_ttl_expires_in_redis(self, redis_client):
        """Set with short TTL, sleep, verify miss."""
        cache = HybridConfigCache(l1_ttl=1, l2_ttl=1, redis_client=redis_client)

        await cache.set("tenant-e", "ephemeral", {"temp": True})

        # Clear L1 to force L2 lookup
        cache._l1.clear()

        # Wait for TTL to expire
        await asyncio.sleep(1.5)

        result = await cache.get("tenant-e", "ephemeral")
        assert result is None
