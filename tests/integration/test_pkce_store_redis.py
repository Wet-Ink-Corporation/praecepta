"""Integration tests for PKCEStore against real Redis.

Verifies store, retrieve-and-delete, and TTL expiry with real Redis.
"""

from __future__ import annotations

import asyncio

import pytest

from praecepta.infra.auth.pkce import PKCEStore


@pytest.mark.integration
class TestPKCEStoreRedis:
    """PKCEStore tests against a real Redis container."""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_store_and_retrieve_round_trip(self, redis_client):
        store = PKCEStore(redis_client, ttl=60)

        await store.store("state-abc", "verifier-xyz", "http://localhost/callback")
        data = await store.retrieve_and_delete("state-abc")

        assert data is not None
        assert data.code_verifier == "verifier-xyz"
        assert data.redirect_uri == "http://localhost/callback"
        assert data.created_at > 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_retrieve_and_delete_is_single_use(self, redis_client):
        store = PKCEStore(redis_client, ttl=60)

        await store.store("state-single", "verifier-1", "http://localhost/cb")

        first = await store.retrieve_and_delete("state-single")
        assert first is not None

        second = await store.retrieve_and_delete("state-single")
        assert second is None

    @pytest.mark.asyncio(loop_scope="function")
    async def test_expired_key_returns_none(self, redis_client):
        store = PKCEStore(redis_client, ttl=1)

        await store.store("state-expire", "verifier-exp", "http://localhost/cb")
        await asyncio.sleep(1.5)

        data = await store.retrieve_and_delete("state-expire")
        assert data is None
