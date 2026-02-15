"""Unit tests for praecepta.infra.fastapi.settings."""

from __future__ import annotations

import pytest

from praecepta.infra.fastapi.settings import AppSettings, CORSSettings


class TestCORSSettings:
    @pytest.mark.unit
    def test_defaults(self) -> None:
        cors = CORSSettings()
        assert cors.allow_origins == ["*"]
        assert cors.allow_methods == ["*"]
        assert cors.allow_headers == ["*"]
        assert cors.allow_credentials is False
        assert cors.expose_headers == ["X-Request-ID"]

    @pytest.mark.unit
    def test_parse_comma_separated_string(self) -> None:
        cors = CORSSettings(
            allow_origins="http://a.com, http://b.com",  # type: ignore[call-arg]
        )
        assert cors.allow_origins == ["http://a.com", "http://b.com"]

    @pytest.mark.unit
    def test_parse_list_passthrough(self) -> None:
        cors = CORSSettings(allow_origins=["http://a.com"])  # type: ignore[call-arg]
        assert cors.allow_origins == ["http://a.com"]


class TestAppSettings:
    @pytest.mark.unit
    def test_defaults(self) -> None:
        settings = AppSettings()
        assert settings.title == "Praecepta Application"
        assert settings.version == "0.1.0"
        assert settings.description == ""
        assert settings.docs_url == "/docs"
        assert settings.debug is False
        assert settings.exclude_groups == frozenset()
        assert settings.exclude_entry_points == frozenset()

    @pytest.mark.unit
    def test_custom_values(self) -> None:
        settings = AppSettings(title="Custom App", version="2.0.0", debug=True)
        assert settings.title == "Custom App"
        assert settings.version == "2.0.0"
        assert settings.debug is True

    @pytest.mark.unit
    def test_cors_nested_default(self) -> None:
        settings = AppSettings()
        assert isinstance(settings.cors, CORSSettings)
        assert settings.cors.allow_origins == ["*"]
