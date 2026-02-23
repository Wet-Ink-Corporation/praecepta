"""Tests for JWKSProvider initialization and jwks_uri construction."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


@pytest.mark.unit
class TestJWKSDiscovery:
    """Test OIDC discovery document integration."""

    @patch("httpx.Client")
    def test_discovery_success_uses_discovered_uri(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "issuer": "https://auth.example.com",
            "jwks_uri": "https://auth.example.com/certs",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(
            return_value=MagicMock(get=MagicMock(return_value=mock_resp))
        )
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_ctx

        provider = JWKSProvider("https://auth.example.com")
        assert provider.jwks_uri == "https://auth.example.com/certs"

    @patch("httpx.Client")
    def test_discovery_issuer_mismatch_falls_back(self, mock_client_cls: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "issuer": "https://other-issuer.example.com",
            "jwks_uri": "https://other-issuer.example.com/certs",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(
            return_value=MagicMock(get=MagicMock(return_value=mock_resp))
        )
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_ctx

        provider = JWKSProvider("https://auth.example.com")
        # Falls back to constructed URI
        assert provider.jwks_uri == "https://auth.example.com/.well-known/jwks.json"

    def test_discovery_failure_falls_back(self) -> None:
        # Default (no mock) — discovery will fail, should fall back gracefully
        provider = JWKSProvider("https://auth.example.com")
        assert provider.jwks_uri == "https://auth.example.com/.well-known/jwks.json"
