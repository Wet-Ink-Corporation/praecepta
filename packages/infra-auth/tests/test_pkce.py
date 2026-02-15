"""Tests for PKCE helpers: derive_code_challenge and PKCEStore."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from praecepta.infra.auth.pkce import PKCEStore, derive_code_challenge


@pytest.mark.unit
class TestDeriveCodeChallenge:
    """Test RFC 7636 S256 code challenge derivation."""

    def test_rfc7636_example_vector(self) -> None:
        """Test against the RFC 7636 Appendix B example."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        assert derive_code_challenge(verifier) == expected

    def test_deterministic(self) -> None:
        """Same verifier always produces same challenge."""
        verifier = "test_verifier_string_with_sufficient_length_abc"
        c1 = derive_code_challenge(verifier)
        c2 = derive_code_challenge(verifier)
        assert c1 == c2

    def test_no_padding(self) -> None:
        """Base64url output must not contain '=' padding."""
        challenge = derive_code_challenge("some_verifier_value_for_testing_padding")
        assert "=" not in challenge


@pytest.mark.unit
class TestPKCEStore:
    """Test PKCEStore store and retrieve_and_delete semantics."""

    @pytest.fixture()
    def mock_redis(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_store_sets_key_with_ttl(self, mock_redis: AsyncMock) -> None:
        store = PKCEStore(mock_redis, ttl=300)
        await store.store("state123", "verifier456", "http://localhost/cb")

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == "pkce:state123"
        assert args[0][1] == 300
        payload = json.loads(args[0][2])
        assert payload["code_verifier"] == "verifier456"
        assert payload["redirect_uri"] == "http://localhost/cb"
        assert "created_at" in payload

    @pytest.mark.asyncio
    async def test_retrieve_and_delete_returns_data(self, mock_redis: AsyncMock) -> None:
        stored = json.dumps(
            {
                "code_verifier": "verifier456",
                "redirect_uri": "http://localhost/cb",
                "created_at": 1700000000.0,
            }
        )
        mock_redis.get.return_value = stored

        store = PKCEStore(mock_redis)
        data = await store.retrieve_and_delete("state123")

        assert data is not None
        assert data.code_verifier == "verifier456"
        assert data.redirect_uri == "http://localhost/cb"
        assert data.created_at == 1700000000.0
        mock_redis.delete.assert_called_once_with("pkce:state123")

    @pytest.mark.asyncio
    async def test_retrieve_and_delete_returns_none_on_missing(self, mock_redis: AsyncMock) -> None:
        mock_redis.get.return_value = None

        store = PKCEStore(mock_redis)
        data = await store.retrieve_and_delete("nonexistent")

        assert data is None
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_and_delete_returns_none_on_corrupt_json(
        self, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = "not-valid-json"

        store = PKCEStore(mock_redis)
        data = await store.retrieve_and_delete("state123")

        assert data is None
        # Still deletes the corrupt key
        mock_redis.delete.assert_called_once_with("pkce:state123")
