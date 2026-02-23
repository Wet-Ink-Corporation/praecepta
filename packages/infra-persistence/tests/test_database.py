"""Unit tests for praecepta.infra.persistence.database."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from praecepta.infra.persistence.database import (
    DatabaseManager,
    DatabaseSettings,
    _get_database_url,
    get_database_manager,
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


class TestDatabasePoolSettings:
    @pytest.mark.unit
    def test_default_async_pool_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            assert settings.async_pool_size == 10
            assert settings.async_max_overflow == 5

    @pytest.mark.unit
    def test_default_sync_pool_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            assert settings.sync_pool_size == 3
            assert settings.sync_max_overflow == 2

    @pytest.mark.unit
    def test_default_shared_pool_values(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            assert settings.pool_timeout == 30
            assert settings.pool_recycle == 3600
            assert settings.echo is False

    @pytest.mark.unit
    def test_pool_settings_from_env(self) -> None:
        env = {
            "DATABASE_ASYNC_POOL_SIZE": "20",
            "DATABASE_ASYNC_MAX_OVERFLOW": "15",
            "DATABASE_SYNC_POOL_SIZE": "8",
            "DATABASE_SYNC_MAX_OVERFLOW": "4",
            "DATABASE_POOL_TIMEOUT": "60",
            "DATABASE_POOL_RECYCLE": "1800",
            "DATABASE_ECHO": "true",
        }
        with patch.dict("os.environ", env, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            assert settings.async_pool_size == 20
            assert settings.async_max_overflow == 15
            assert settings.sync_pool_size == 8
            assert settings.sync_max_overflow == 4
            assert settings.pool_timeout == 60
            assert settings.pool_recycle == 1800
            assert settings.echo is True


class TestDatabaseManager:
    @pytest.mark.unit
    def test_manager_stores_settings(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = DatabaseSettings()  # type: ignore[call-arg]
            manager = DatabaseManager(settings)
            assert manager.settings is settings

    @pytest.mark.unit
    def test_two_managers_with_different_configs(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            s1 = DatabaseSettings(name="db1")  # type: ignore[call-arg]
            s2 = DatabaseSettings(name="db2")  # type: ignore[call-arg]
            m1 = DatabaseManager(s1)
            m2 = DatabaseManager(s2)
            assert m1.settings.name == "db1"
            assert m2.settings.name == "db2"
            assert m1 is not m2


class TestGetDatabaseManager:
    @pytest.mark.unit
    def test_returns_manager_instance(self) -> None:
        get_database_manager.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            manager = get_database_manager()
            assert isinstance(manager, DatabaseManager)

    @pytest.mark.unit
    def test_cached_returns_same_instance(self) -> None:
        get_database_manager.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            m1 = get_database_manager()
            m2 = get_database_manager()
            assert m1 is m2


class TestGetDatabaseUrl:
    @pytest.mark.unit
    def test_returns_valid_url(self) -> None:
        get_database_manager.cache_clear()
        with patch.dict("os.environ", {}, clear=True):
            url = _get_database_url()
            assert url.startswith("postgresql+psycopg://")
