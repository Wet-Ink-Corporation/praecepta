"""Tests for auth lifespan hook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from praecepta.infra.auth.lifespan import _auth_lifespan, lifespan_contribution
from praecepta.infra.auth.settings import AuthSettings


@pytest.mark.unit
class TestAuthLifespan:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_skips_jwks_when_no_issuer(self) -> None:
        app = MagicMock()
        # Use spec to prevent auto-creation of attributes
        app.state = MagicMock(spec=[])
        settings = AuthSettings(issuer="", dev_bypass=False)
        with patch("praecepta.infra.auth.lifespan.get_auth_settings", return_value=settings):
            async with _auth_lifespan(app):
                pass
        # Should not set jwks_provider
        assert not hasattr(app.state, "jwks_provider")

    @pytest.mark.asyncio(loop_scope="function")
    async def test_skips_jwks_when_dev_bypass(self) -> None:
        app = MagicMock()
        settings = AuthSettings(issuer="https://auth.example.com", dev_bypass=True)
        with patch("praecepta.infra.auth.lifespan.get_auth_settings", return_value=settings):
            async with _auth_lifespan(app):
                pass

    @pytest.mark.asyncio(loop_scope="function")
    async def test_initializes_jwks_when_issuer_set(self) -> None:
        app = MagicMock()
        settings = AuthSettings(issuer="https://auth.example.com", dev_bypass=False)
        mock_provider = MagicMock()

        with (
            patch("praecepta.infra.auth.lifespan.get_auth_settings", return_value=settings),
            patch("praecepta.infra.auth.jwks.JWKSProvider", return_value=mock_provider) as mock_cls,
        ):
            async with _auth_lifespan(app):
                mock_cls.assert_called_once_with("https://auth.example.com", cache_ttl=300)
                assert app.state.jwks_provider is mock_provider

    def test_contribution_priority(self) -> None:
        assert lifespan_contribution.priority == 60
