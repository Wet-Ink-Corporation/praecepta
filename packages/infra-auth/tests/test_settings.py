"""Tests for AuthSettings env loading and validation."""

from __future__ import annotations

import pytest

from praecepta.infra.auth.settings import AuthSettings, get_auth_settings


@pytest.mark.unit
class TestAuthSettings:
    """Test AuthSettings defaults and env loading."""

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear any existing AUTH_ env vars
        monkeypatch.delenv("AUTH_ISSUER", raising=False)
        monkeypatch.delenv("AUTH_AUDIENCE", raising=False)
        monkeypatch.delenv("AUTH_DEV_BYPASS", raising=False)

        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.issuer == ""
        assert settings.audience == "api"
        assert settings.jwks_cache_ttl == 300
        assert settings.dev_bypass is False
        assert settings.oauth_client_id == ""
        assert settings.oauth_client_secret == ""

    def test_env_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_ISSUER", "https://auth.test.com")
        monkeypatch.setenv("AUTH_AUDIENCE", "my-api")
        monkeypatch.setenv("AUTH_DEV_BYPASS", "true")

        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.issuer == "https://auth.test.com"
        assert settings.audience == "my-api"
        assert settings.dev_bypass is True

    def test_is_oauth_configured_false_by_default(self) -> None:
        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.is_oauth_configured() is False

    def test_is_oauth_configured_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_OAUTH_CLIENT_ID", "cid")
        monkeypatch.setenv("AUTH_OAUTH_CLIENT_SECRET", "csec")
        monkeypatch.setenv("AUTH_OAUTH_REDIRECT_URI", "http://localhost/cb")

        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.is_oauth_configured() is True

    def test_validate_oauth_config_missing_client_id(self) -> None:
        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        with pytest.raises(ValueError, match="AUTH_OAUTH_CLIENT_ID"):
            settings.validate_oauth_config()

    def test_validate_oauth_config_missing_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_OAUTH_CLIENT_ID", "cid")
        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        with pytest.raises(ValueError, match="AUTH_OAUTH_CLIENT_SECRET"):
            settings.validate_oauth_config()

    def test_validate_oauth_config_invalid_redirect_uri(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AUTH_OAUTH_CLIENT_ID", "cid")
        monkeypatch.setenv("AUTH_OAUTH_CLIENT_SECRET", "csec")
        monkeypatch.setenv("AUTH_OAUTH_REDIRECT_URI", "ftp://bad")

        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        with pytest.raises(ValueError, match="valid HTTP"):
            settings.validate_oauth_config()

    def test_validate_oauth_config_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTH_OAUTH_CLIENT_ID", "cid")
        monkeypatch.setenv("AUTH_OAUTH_CLIENT_SECRET", "csec")
        monkeypatch.setenv("AUTH_OAUTH_REDIRECT_URI", "https://example.com/cb")
        monkeypatch.setenv("AUTH_OAUTH_SCOPES", "openid profile")

        settings = AuthSettings(_env_file=None)  # type: ignore[call-arg]
        settings.validate_oauth_config()  # Should not raise

    def test_get_auth_settings_caching(self) -> None:
        get_auth_settings.cache_clear()
        s1 = get_auth_settings()
        s2 = get_auth_settings()
        assert s1 is s2
        get_auth_settings.cache_clear()
