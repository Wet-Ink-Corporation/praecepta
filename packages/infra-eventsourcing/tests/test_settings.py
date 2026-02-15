"""Tests for EventSourcingSettings configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from praecepta.infra.eventsourcing.settings import EventSourcingSettings


@pytest.mark.unit
class TestEventSourcingSettings:
    """Tests for EventSourcingSettings validation and defaults."""

    def _make_settings(self, **overrides: object) -> EventSourcingSettings:
        """Create settings with required fields and optional overrides."""
        defaults: dict[str, object] = {
            "postgres_dbname": "testdb",
            "postgres_user": "testuser",
            "postgres_password": "testpass",
        }
        defaults.update(overrides)
        return EventSourcingSettings(**defaults)  # type: ignore[arg-type]

    def test_required_fields(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_dbname == "testdb"
        assert settings.postgres_user == "testuser"
        assert settings.postgres_password == "testpass"

    def test_default_host(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_host == "localhost"

    def test_default_port(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_port == 5432

    def test_default_pool_size(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_pool_size == 5

    def test_default_max_overflow(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_max_overflow == 10

    def test_default_conn_max_age(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_conn_max_age == 600

    def test_default_connect_timeout(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_connect_timeout == 30

    def test_default_create_table(self) -> None:
        settings = self._make_settings()
        assert settings.create_table is True

    def test_default_schema(self) -> None:
        settings = self._make_settings()
        assert settings.postgres_schema == "public"

    def test_default_persistence_module(self) -> None:
        settings = self._make_settings()
        assert settings.persistence_module == "eventsourcing.postgres"

    def test_custom_pool_size(self) -> None:
        settings = self._make_settings(postgres_pool_size=20)
        assert settings.postgres_pool_size == 20

    def test_custom_host(self) -> None:
        settings = self._make_settings(postgres_host="db.example.com")
        assert settings.postgres_host == "db.example.com"

    def test_custom_port(self) -> None:
        settings = self._make_settings(postgres_port=15432)
        assert settings.postgres_port == 15432

    def test_port_validation_lower_bound(self) -> None:
        with pytest.raises(ValueError):
            self._make_settings(postgres_port=0)

    def test_port_validation_upper_bound(self) -> None:
        with pytest.raises(ValueError):
            self._make_settings(postgres_port=70000)

    def test_port_valid_boundaries(self) -> None:
        settings_low = self._make_settings(postgres_port=1)
        assert settings_low.postgres_port == 1

        settings_high = self._make_settings(postgres_port=65535)
        assert settings_high.postgres_port == 65535

    def test_pool_size_validation(self) -> None:
        with pytest.raises(ValueError):
            self._make_settings(postgres_pool_size=0)

        with pytest.raises(ValueError):
            self._make_settings(postgres_pool_size=51)

    def test_max_overflow_validation(self) -> None:
        with pytest.raises(ValueError):
            self._make_settings(postgres_max_overflow=-1)

        with pytest.raises(ValueError):
            self._make_settings(postgres_max_overflow=101)


@pytest.mark.unit
class TestEventSourcingSettingsToEnvDict:
    """Tests for to_env_dict() method."""

    def test_to_env_dict_basic_fields(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="mydb",
            postgres_user="user",
            postgres_password="pass",
        )
        env = settings.to_env_dict()

        assert env["POSTGRES_DBNAME"] == "mydb"
        assert env["POSTGRES_USER"] == "user"
        assert env["POSTGRES_PASSWORD"] == "pass"
        assert env["POSTGRES_HOST"] == "localhost"
        assert env["POSTGRES_PORT"] == "5432"

    def test_to_env_dict_persistence_module(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="db",
            postgres_user="user",
            postgres_password="pass",
        )
        env = settings.to_env_dict()
        assert env["PERSISTENCE_MODULE"] == "eventsourcing.postgres"

    def test_to_env_dict_pool_settings(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="db",
            postgres_user="user",
            postgres_password="pass",
            postgres_pool_size=10,
            postgres_max_overflow=20,
        )
        env = settings.to_env_dict()
        assert env["POSTGRES_POOL_SIZE"] == "10"
        assert env["POSTGRES_MAX_OVERFLOW"] == "20"

    def test_to_env_dict_create_table(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="db",
            postgres_user="user",
            postgres_password="pass",
            create_table=True,
        )
        env = settings.to_env_dict()
        assert env["CREATE_TABLE"] == "true"

    def test_to_env_dict_create_table_false(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="db",
            postgres_user="user",
            postgres_password="pass",
            create_table=False,
        )
        env = settings.to_env_dict()
        assert env["CREATE_TABLE"] == "false"

    def test_to_env_dict_pre_ping_enabled(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="db",
            postgres_user="user",
            postgres_password="pass",
            postgres_pre_ping=True,
        )
        env = settings.to_env_dict()
        assert env["POSTGRES_PRE_PING"] == "y"

    def test_to_env_dict_pre_ping_disabled(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="db",
            postgres_user="user",
            postgres_password="pass",
            postgres_pre_ping=False,
        )
        env = settings.to_env_dict()
        assert env["POSTGRES_PRE_PING"] == ""

    def test_to_env_dict_all_string_values(self) -> None:
        settings = EventSourcingSettings(
            postgres_dbname="db",
            postgres_user="user",
            postgres_password="pass",
        )
        env = settings.to_env_dict()
        for key, value in env.items():
            assert isinstance(value, str), f"{key} should be str, got {type(value)}"


@pytest.mark.unit
class TestEventSourcingSettingsProductionWarning:
    """Tests for production CREATE_TABLE warning."""

    def test_warns_in_production_with_create_table_true(self) -> None:
        with (
            patch.dict(os.environ, {"ENVIRONMENT": "production"}),
            pytest.warns(UserWarning, match="CREATE_TABLE=true in production"),
        ):
            EventSourcingSettings(
                postgres_dbname="db",
                postgres_user="user",
                postgres_password="pass",
                create_table=True,
            )

    def test_no_warning_in_development(self) -> None:
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            # Should not warn
            EventSourcingSettings(
                postgres_dbname="db",
                postgres_user="user",
                postgres_password="pass",
                create_table=True,
            )
