"""Unit tests for praecepta.infra.persistence.lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from praecepta.foundation.application import LifespanContribution
from praecepta.infra.persistence.lifespan import (
    _persistence_lifespan,
    lifespan_contribution,
)


def _mock_manager() -> tuple[MagicMock, AsyncMock]:
    """Create a mock DatabaseManager with async engine.connect() context manager."""
    mock_conn = AsyncMock()

    @asynccontextmanager
    async def _connect():  # type: ignore[no-untyped-def]
        yield mock_conn

    mock_engine = MagicMock()
    mock_engine.connect = _connect

    # Provide realistic settings for connection budget calculation
    mock_settings = MagicMock()
    mock_settings.async_pool_size = 10
    mock_settings.async_max_overflow = 5
    mock_settings.sync_pool_size = 3
    mock_settings.sync_max_overflow = 2

    mock_mgr = MagicMock()
    mock_mgr.get_engine.return_value = mock_engine
    mock_mgr.settings = mock_settings
    mock_mgr.dispose = AsyncMock()
    return mock_mgr, mock_conn


@pytest.mark.unit
class TestLifespanContribution:
    def test_is_lifespan_contribution(self) -> None:
        assert isinstance(lifespan_contribution, LifespanContribution)

    def test_priority_is_75(self) -> None:
        assert lifespan_contribution.priority == 75

    def test_hook_is_callable(self) -> None:
        assert callable(lifespan_contribution.hook)


@pytest.mark.unit
class TestPersistenceLifespan:
    @pytest.mark.asyncio
    @patch("praecepta.infra.persistence.lifespan.get_redis_factory")
    @patch("praecepta.infra.persistence.lifespan.register_tenant_context_handler")
    @patch("praecepta.infra.persistence.lifespan.get_database_manager")
    async def test_startup_registers_tenant_handler(
        self,
        mock_get_manager: MagicMock,
        mock_register: MagicMock,
        mock_get_redis: MagicMock,
    ) -> None:
        mock_mgr, _ = _mock_manager()
        mock_get_manager.return_value = mock_mgr
        mock_get_redis.return_value = AsyncMock()

        async with _persistence_lifespan(MagicMock()):
            mock_register.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.persistence.lifespan.get_redis_factory")
    @patch("praecepta.infra.persistence.lifespan.register_tenant_context_handler")
    @patch("praecepta.infra.persistence.lifespan.get_database_manager")
    async def test_startup_runs_health_check(
        self,
        mock_get_manager: MagicMock,
        mock_register: MagicMock,
        mock_get_redis: MagicMock,
    ) -> None:
        mock_mgr, mock_conn = _mock_manager()
        mock_get_manager.return_value = mock_mgr
        mock_get_redis.return_value = AsyncMock()

        async with _persistence_lifespan(MagicMock()):
            mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.persistence.lifespan.get_redis_factory")
    @patch("praecepta.infra.persistence.lifespan.register_tenant_context_handler")
    @patch("praecepta.infra.persistence.lifespan.get_database_manager")
    async def test_shutdown_disposes_engines(
        self,
        mock_get_manager: MagicMock,
        mock_register: MagicMock,
        mock_get_redis: MagicMock,
    ) -> None:
        mock_mgr, _ = _mock_manager()
        mock_get_manager.return_value = mock_mgr
        mock_get_redis.return_value = AsyncMock()

        async with _persistence_lifespan(MagicMock()):
            mock_mgr.dispose.assert_not_called()

        mock_mgr.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.persistence.lifespan.get_redis_factory")
    @patch("praecepta.infra.persistence.lifespan.register_tenant_context_handler")
    @patch("praecepta.infra.persistence.lifespan.get_database_manager")
    async def test_shutdown_closes_redis(
        self,
        mock_get_manager: MagicMock,
        mock_register: MagicMock,
        mock_get_redis: MagicMock,
    ) -> None:
        mock_mgr, _ = _mock_manager()
        mock_get_manager.return_value = mock_mgr
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        async with _persistence_lifespan(MagicMock()):
            mock_redis.close.assert_not_called()

        mock_redis.close.assert_awaited_once()
