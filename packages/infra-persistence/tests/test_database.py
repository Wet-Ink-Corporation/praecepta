"""Unit tests for praecepta.infra.persistence.database."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from praecepta.infra.persistence.database import (
    DatabaseSettings,
    _get_database_url,
)


class TestDatabaseSettings:
    @pytest.mark.unit
    def test_default_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            assert settings.host == "localhost"
            assert settings.port == 5432
            assert settings.user == "postgres"
            assert settings.password == "postgres"
            assert settings.name == "app"

    @pytest.mark.unit
    def test_database_url_property(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            url = settings.database_url
            assert url == "postgresql+psycopg://postgres:postgres@localhost:5432/app"

    @pytest.mark.unit
    def test_custom_values_from_env(self) -> None:
        env = {
            "DATABASE_HOST": "db.example.com",
            "DATABASE_PORT": "5433",
            "DATABASE_USER": "myuser",
            "DATABASE_PASSWORD": "mypass",
            "DATABASE_NAME": "mydb",
        }
        with patch.dict("os.environ", env, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            assert settings.host == "db.example.com"
            assert settings.port == 5433
            expected = "postgresql+psycopg://myuser:mypass@db.example.com:5433/mydb"
            assert settings.database_url == expected

    @pytest.mark.unit
    def test_password_hidden_in_repr(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            repr_str = repr(settings)
            assert "postgres" not in repr_str or "password" not in repr_str


class TestGetDatabaseUrl:
    @pytest.mark.unit
    def test_returns_valid_url(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            url = _get_database_url()
            assert url.startswith("postgresql+psycopg://")
