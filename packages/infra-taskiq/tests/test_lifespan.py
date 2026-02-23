"""Unit tests for praecepta.infra.taskiq.lifespan."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from praecepta.foundation.application import LifespanContribution
from praecepta.infra.taskiq.lifespan import _taskiq_lifespan, lifespan_contribution


@pytest.mark.unit
class TestLifespanContribution:
    def test_is_lifespan_contribution(self) -> None:
        assert isinstance(lifespan_contribution, LifespanContribution)

    def test_priority_is_150(self) -> None:
        assert lifespan_contribution.priority == 150

    def test_hook_is_callable(self) -> None:
        assert callable(lifespan_contribution.hook)


@pytest.mark.unit
class TestTaskIQLifespan:
    @pytest.mark.asyncio
    @patch("praecepta.infra.taskiq.lifespan.get_broker")
    async def test_startup_calls_broker_startup(
        self,
        mock_get_broker: MagicMock,
    ) -> None:
        mock_broker = AsyncMock()
        mock_get_broker.return_value = mock_broker

        async with _taskiq_lifespan(MagicMock()):
            mock_broker.startup.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.taskiq.lifespan.get_broker")
    async def test_shutdown_calls_broker_shutdown(
        self,
        mock_get_broker: MagicMock,
    ) -> None:
        mock_broker = AsyncMock()
        mock_get_broker.return_value = mock_broker

        async with _taskiq_lifespan(MagicMock()):
            mock_broker.shutdown.assert_not_called()

        mock_broker.shutdown.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.taskiq.lifespan.get_broker")
    async def test_shutdown_called_on_exception(
        self,
        mock_get_broker: MagicMock,
    ) -> None:
        mock_broker = AsyncMock()
        mock_get_broker.return_value = mock_broker

        with pytest.raises(ValueError, match="test error"):
            async with _taskiq_lifespan(MagicMock()):
                raise ValueError("test error")

        mock_broker.shutdown.assert_awaited_once()
