"""Tests for JWKSProvider initialization and jwks_uri construction."""

from __future__ import annotations

import pytest

from praecepta.infra.auth.jwks import JWKSProvider


@pytest.mark.unit
class TestJWKSProviderInit:
    """Test JWKSProvider initialization and properties."""

    def test_empty_issuer_url_raises(self) -> None:
        with pytest.raises(ValueError, match="OIDC issuer URL is required"):
            JWKSProvider("")

    def test_jwks_uri_constructed_from_issuer(self) -> None:
        provider = JWKSProvider("https://auth.example.com")
        assert provider.jwks_uri == "https://auth.example.com/.well-known/jwks.json"

    def test_trailing_slash_stripped(self) -> None:
        provider = JWKSProvider("https://auth.example.com/")
        assert provider.issuer_url == "https://auth.example.com"
        assert provider.jwks_uri == "https://auth.example.com/.well-known/jwks.json"

    def test_issuer_url_property(self) -> None:
        provider = JWKSProvider("https://auth.example.com")
        assert provider.issuer_url == "https://auth.example.com"

    def test_custom_cache_ttl(self) -> None:
        # Just verify it doesn't raise -- TTL is passed to PyJWKClient internally
        provider = JWKSProvider("https://auth.example.com", cache_ttl=600)
        assert provider.jwks_uri == "https://auth.example.com/.well-known/jwks.json"
