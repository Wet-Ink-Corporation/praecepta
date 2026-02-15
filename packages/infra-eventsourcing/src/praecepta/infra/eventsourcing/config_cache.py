"""Hybrid L1/L2 cache for tenant configuration lookups.

L1: In-memory (cachetools.TTLCache, 5min TTL, per-process)
L2: Redis (1hr TTL, shared across processes)

Cache key format: tenant:{tenant_id}:config:{config_key}
"""

from __future__ import annotations

import json
from typing import Any

from cachetools import TTLCache  # type: ignore[import-untyped]


class HybridConfigCache:
    """Two-level configuration cache.

    L1 (in-memory): <1ms access, process-local, 5min TTL
    L2 (Redis): 1-5ms access, shared, 1hr TTL

    Event-driven invalidation on config update events.

    Args:
        l1_maxsize: Maximum L1 cache entries (default: 10,000).
        l1_ttl: L1 TTL in seconds (default: 300 = 5 minutes).
        l2_ttl: L2 TTL in seconds (default: 3600 = 1 hour).
        redis_client: Optional async Redis client. If None, L2 is disabled.
    """

    def __init__(
        self,
        l1_maxsize: int = 10_000,
        l1_ttl: int = 300,
        l2_ttl: int = 3600,
        redis_client: Any | None = None,
    ) -> None:
        self._l1: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=l1_maxsize, ttl=l1_ttl)
        self._l2_ttl = l2_ttl
        self._redis = redis_client

    def _cache_key(self, tenant_id: str, key: str) -> str:
        """Build cache key with tenant isolation prefix."""
        return f"tenant:{tenant_id}:config:{key}"

    async def get(self, tenant_id: str, key: str) -> dict[str, Any] | None:
        """Get from L1, fallback to L2, return None on miss.

        On L2 hit, promotes value to L1.

        Args:
            tenant_id: Tenant slug.
            key: Configuration key string.

        Returns:
            Config value dict or None on miss.
        """
        cache_key = self._cache_key(tenant_id, key)

        # L1 lookup
        l1_value: dict[str, Any] | None = self._l1.get(cache_key)
        if l1_value is not None:
            return l1_value

        # L2 lookup
        if self._redis is not None:
            raw = await self._redis.get(cache_key)
            if raw is not None:
                l2_value: dict[str, Any] = json.loads(raw)
                # Promote to L1
                self._l1[cache_key] = l2_value
                return l2_value

        return None

    async def set(self, tenant_id: str, key: str, value: dict[str, Any]) -> None:
        """Write to both L1 and L2.

        Args:
            tenant_id: Tenant slug.
            key: Configuration key string.
            value: Config value dict.
        """
        cache_key = self._cache_key(tenant_id, key)

        # L1
        self._l1[cache_key] = value

        # L2
        if self._redis is not None:
            await self._redis.set(
                cache_key,
                json.dumps(value),
                ex=self._l2_ttl,
            )

    async def invalidate(self, tenant_id: str, key: str) -> None:
        """Remove from both L1 and L2.

        Args:
            tenant_id: Tenant slug.
            key: Configuration key string.
        """
        cache_key = self._cache_key(tenant_id, key)

        # L1
        self._l1.pop(cache_key, None)

        # L2
        if self._redis is not None:
            await self._redis.delete(cache_key)

    async def invalidate_tenant(self, tenant_id: str) -> None:
        """Remove all entries for a tenant (bulk invalidation).

        L1: Iterate and remove matching keys.
        L2: Use Redis SCAN + DEL pattern.

        Args:
            tenant_id: Tenant slug.
        """
        prefix = f"tenant:{tenant_id}:config:"

        # L1: Remove matching keys
        keys_to_remove = [k for k in self._l1 if k.startswith(prefix)]
        for k in keys_to_remove:
            self._l1.pop(k, None)

        # L2: Scan and delete
        if self._redis is not None:
            cursor: int = 0
            while True:
                cursor, keys = await self._redis.scan(cursor=cursor, match=f"{prefix}*", count=100)
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
