"""Tests for EventStoreFactory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from praecepta.infra.eventsourcing.event_store import EventStoreFactory, get_event_store
from praecepta.infra.eventsourcing.settings import EventSourcingSettings


@pytest.mark.unit
class TestEventStoreFactory:
    """Tests for EventStoreFactory construction."""

    def _make_settings(self, **overrides: object) -> EventSourcingSettings:
        defaults: dict[str, object] = {
            "postgres_dbname": "testdb",
            "postgres_user": "testuser",
            "postgres_password": "testpass",
        }
        defaults.update(overrides)
        return EventSourcingSettings(**defaults)  # type: ignore[arg-type]

    def test_init_stores_settings(self) -> None:
        settings = self._make_settings()
        factory = EventStoreFactory(settings)
        assert factory._settings is settings

    def test_infrastructure_factory_starts_none(self) -> None:
        settings = self._make_settings()
        factory = EventStoreFactory(settings)
        assert factory._infrastructure_factory is None

    def test_from_database_url(self) -> None:
        factory = EventStoreFactory.from_database_url("postgresql://user:pass@localhost:5432/mydb")
        assert factory._settings.postgres_dbname == "mydb"
        assert factory._settings.postgres_user == "user"
        assert factory._settings.postgres_password == "pass"
        assert factory._settings.postgres_host == "localhost"
        assert factory._settings.postgres_port == 5432

    def test_from_database_url_with_overrides(self) -> None:
        factory = EventStoreFactory.from_database_url(
            "postgresql://user:pass@localhost:5432/mydb",
            postgres_pool_size=20,
        )
        assert factory._settings.postgres_pool_size == 20

    def test_from_database_url_custom_port(self) -> None:
        factory = EventStoreFactory.from_database_url("postgresql://user:pass@localhost:15432/mydb")
        assert factory._settings.postgres_port == 15432

    def test_close_when_not_initialized(self) -> None:
        settings = self._make_settings()
        factory = EventStoreFactory(settings)
        # Should not raise
        factory.close()
        assert factory._infrastructure_factory is None

    def test_close_calls_factory_close(self) -> None:
        settings = self._make_settings()
        factory = EventStoreFactory(settings)
        mock_infra_factory = MagicMock()
        factory._infrastructure_factory = mock_infra_factory

        factory.close()

        mock_infra_factory.close.assert_called_once()
        assert factory._infrastructure_factory is None

    @patch("praecepta.infra.eventsourcing.event_store.PostgresInfrastructureFactory")
    def test_recorder_creates_infrastructure_factory(self, mock_factory_class: MagicMock) -> None:
        settings = self._make_settings()
        factory = EventStoreFactory(settings)

        mock_infra = MagicMock()
        mock_factory_class.construct.return_value = mock_infra

        _recorder = factory.recorder

        mock_factory_class.construct.assert_called_once()
        mock_infra.application_recorder.assert_called_once()

    @patch("praecepta.infra.eventsourcing.event_store.PostgresInfrastructureFactory")
    def test_recorder_reuses_infrastructure_factory(self, mock_factory_class: MagicMock) -> None:
        settings = self._make_settings()
        factory = EventStoreFactory(settings)

        mock_infra = MagicMock()
        mock_factory_class.construct.return_value = mock_infra

        _recorder1 = factory.recorder
        _recorder2 = factory.recorder

        # Factory.construct() should be called only once (lazy init)
        mock_factory_class.construct.assert_called_once()


@pytest.mark.unit
class TestEventStoreFactoryFromEnv:
    """Tests for EventStoreFactory.from_env()."""

    def test_from_env_with_database_url(self) -> None:
        env = {
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb",
        }
        with patch.dict("os.environ", env, clear=False):
            factory = EventStoreFactory.from_env()
            assert factory._settings.postgres_dbname == "mydb"
            assert factory._settings.postgres_user == "user"

    def test_from_env_postgres_vars_override_database_url(self) -> None:
        env = {
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb",
            "POSTGRES_DBNAME": "overridden_db",
        }
        with patch.dict("os.environ", env, clear=False):
            factory = EventStoreFactory.from_env()
            assert factory._settings.postgres_dbname == "overridden_db"

    def test_from_env_with_individual_vars(self) -> None:
        env = {
            "POSTGRES_DBNAME": "testdb",
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
            "POSTGRES_HOST": "dbhost",
            "POSTGRES_PORT": "15432",
        }
        # Remove DATABASE_URL if present
        with (
            patch.dict("os.environ", env, clear=False),
            patch("os.getenv", side_effect=lambda k, d=None: env.get(k, d)),
        ):
            factory = EventStoreFactory.from_env()
            assert factory._settings.postgres_dbname == "testdb"


@pytest.mark.unit
class TestGetEventStore:
    """Tests for get_event_store() singleton."""

    def test_get_event_store_returns_factory(self) -> None:
        env = {
            "POSTGRES_DBNAME": "testdb",
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
        }
        # Clear the lru_cache before test
        get_event_store.cache_clear()

        with patch.dict("os.environ", env, clear=False):
            factory = get_event_store()
            assert isinstance(factory, EventStoreFactory)

        # Clean up
        get_event_store.cache_clear()

    def test_get_event_store_is_cached(self) -> None:
        env = {
            "POSTGRES_DBNAME": "testdb",
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
        }
        get_event_store.cache_clear()

        with patch.dict("os.environ", env, clear=False):
            factory1 = get_event_store()
            factory2 = get_event_store()
            assert factory1 is factory2

        get_event_store.cache_clear()
