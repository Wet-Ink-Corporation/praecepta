"""Tests for event store lifespan hook and environment bridging."""

from __future__ import annotations

import os
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from praecepta.foundation.application import LifespanContribution
from praecepta.infra.eventsourcing.lifespan import (
    _bridge_settings_to_environ,
    lifespan_contribution,
)

# ---------------------------------------------------------------------------
# Tests: module-level contribution instance
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLifespanContribution:
    def test_is_lifespan_contribution(self) -> None:
        assert isinstance(lifespan_contribution, LifespanContribution)

    def test_priority_is_100(self) -> None:
        assert lifespan_contribution.priority == 100

    def test_hook_is_callable(self) -> None:
        assert callable(lifespan_contribution.hook)


# ---------------------------------------------------------------------------
# Tests: _bridge_settings_to_environ
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBridgeSettingsToEnviron:
    """Tests for _bridge_settings_to_environ() function."""

    _REQUIRED_POSTGRES_VARS: ClassVar[dict[str, str]] = {
        "POSTGRES_DBNAME": "testdb",
        "POSTGRES_USER": "testuser",
        "POSTGRES_PASSWORD": "testpass",
    }

    def test_bridges_persistence_module_when_absent(self) -> None:
        """PERSISTENCE_MODULE should be set from settings default."""
        clean_env = {**self._REQUIRED_POSTGRES_VARS}
        # Remove PERSISTENCE_MODULE if present
        clean_env.pop("PERSISTENCE_MODULE", None)

        with patch.dict(os.environ, clean_env, clear=True):
            _bridge_settings_to_environ()
            assert os.environ["PERSISTENCE_MODULE"] == "eventsourcing.postgres"

    def test_does_not_overwrite_existing_persistence_module(self) -> None:
        """Explicit env vars should take precedence over settings defaults."""
        env = {
            **self._REQUIRED_POSTGRES_VARS,
            "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        }

        with patch.dict(os.environ, env, clear=True):
            _bridge_settings_to_environ()
            assert os.environ["PERSISTENCE_MODULE"] == "eventsourcing.sqlite"

    def test_bridges_postgres_host_when_absent(self) -> None:
        """POSTGRES_HOST should be bridged from settings default."""
        env = {**self._REQUIRED_POSTGRES_VARS}
        env.pop("POSTGRES_HOST", None)

        with patch.dict(os.environ, env, clear=True):
            _bridge_settings_to_environ()
            assert os.environ["POSTGRES_HOST"] == "localhost"

    def test_does_not_overwrite_existing_postgres_host(self) -> None:
        env = {
            **self._REQUIRED_POSTGRES_VARS,
            "POSTGRES_HOST": "db.example.com",
        }

        with patch.dict(os.environ, env, clear=True):
            _bridge_settings_to_environ()
            assert os.environ["POSTGRES_HOST"] == "db.example.com"

    def test_bridges_multiple_keys(self) -> None:
        """All bridge keys should be populated when absent."""
        env = {**self._REQUIRED_POSTGRES_VARS}

        with patch.dict(os.environ, env, clear=True):
            _bridge_settings_to_environ()

            assert os.environ["PERSISTENCE_MODULE"] == "eventsourcing.postgres"
            assert os.environ["POSTGRES_HOST"] == "localhost"
            assert os.environ["POSTGRES_PORT"] == "5432"
            assert os.environ["POSTGRES_SCHEMA"] == "public"
            assert os.environ["CREATE_TABLE"] == "true"

    def test_does_not_crash_when_settings_cannot_load(self) -> None:
        """Missing required fields -> bridge logs warning and returns."""
        # No POSTGRES_* vars at all
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise
            _bridge_settings_to_environ()
            # PERSISTENCE_MODULE should NOT be set (settings failed to load)
            assert "PERSISTENCE_MODULE" not in os.environ

    def test_logs_warning_when_persistence_module_absent(self) -> None:
        """A warning should be logged when PERSISTENCE_MODULE is missing."""
        env = {**self._REQUIRED_POSTGRES_VARS}

        with (
            patch.dict(os.environ, env, clear=True),
            patch("praecepta.infra.eventsourcing.lifespan.logger") as mock_logger,
        ):
            _bridge_settings_to_environ()
            mock_logger.warning.assert_any_call(
                "PERSISTENCE_MODULE not set in environment. "
                "Bridging from EventSourcingSettings (default: eventsourcing.postgres). "
                "Set PERSISTENCE_MODULE explicitly in production.",
            )

    def test_no_persistence_warning_when_module_set(self) -> None:
        """No PERSISTENCE_MODULE warning when it's already in env."""
        env = {
            **self._REQUIRED_POSTGRES_VARS,
            "PERSISTENCE_MODULE": "eventsourcing.postgres",
        }

        with (
            patch.dict(os.environ, env, clear=True),
            patch("praecepta.infra.eventsourcing.lifespan.logger") as mock_logger,
        ):
            _bridge_settings_to_environ()
            # The specific "not set" warning should NOT have been called
            for call_args in mock_logger.warning.call_args_list:
                assert "PERSISTENCE_MODULE not set" not in str(call_args)


# ---------------------------------------------------------------------------
# Tests: event_store_lifespan (async context manager)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEventStoreLifespan:
    @pytest.mark.asyncio
    async def test_calls_bridge_and_initialises_store(self) -> None:
        """Lifespan should bridge settings, get store, yield, then close."""
        from praecepta.infra.eventsourcing.lifespan import event_store_lifespan

        mock_store = MagicMock()

        with (
            patch(
                "praecepta.infra.eventsourcing.lifespan._bridge_settings_to_environ"
            ) as mock_bridge,
            patch(
                "praecepta.infra.eventsourcing.event_store.get_event_store",
                return_value=mock_store,
            ),
        ):
            async with event_store_lifespan(MagicMock()):
                mock_bridge.assert_called_once()
                mock_store.close.assert_not_called()

            mock_store.close.assert_called_once()
