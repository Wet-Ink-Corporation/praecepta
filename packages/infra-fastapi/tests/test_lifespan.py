"""Unit tests for praecepta.infra.fastapi.lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from praecepta.foundation.application.contributions import LifespanContribution
from praecepta.infra.fastapi.lifespan import compose_lifespan


class TestComposeLifespan:
    @pytest.mark.unit
    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_hooks_yields_without_error(self) -> None:
        lifespan = compose_lifespan([])
        mock_app = MagicMock()
        async with lifespan(mock_app):  # type: ignore[arg-type]
            pass  # Should not raise

    @pytest.mark.unit
    @pytest.mark.asyncio(loop_scope="function")
    async def test_hooks_execute_in_priority_order(self) -> None:
        order: list[str] = []

        @asynccontextmanager
        async def hook_a(app: object) -> AsyncIterator[None]:
            order.append("a_start")
            yield
            order.append("a_stop")

        @asynccontextmanager
        async def hook_b(app: object) -> AsyncIterator[None]:
            order.append("b_start")
            yield
            order.append("b_stop")

        hooks = [
            LifespanContribution(hook=hook_b, priority=200),
            LifespanContribution(hook=hook_a, priority=100),
        ]

        lifespan = compose_lifespan(hooks)
        mock_app = MagicMock()
        async with lifespan(mock_app):  # type: ignore[arg-type]
            assert order == ["a_start", "b_start"]

        # Shutdown is LIFO (AsyncExitStack)
        assert order == ["a_start", "b_start", "b_stop", "a_stop"]

    @pytest.mark.unit
    @pytest.mark.asyncio(loop_scope="function")
    async def test_app_is_passed_to_hooks(self) -> None:
        received_apps: list[object] = []

        @asynccontextmanager
        async def hook(app: object) -> AsyncIterator[None]:
            received_apps.append(app)
            yield

        lifespan = compose_lifespan([LifespanContribution(hook=hook)])
        mock_app = MagicMock()
        async with lifespan(mock_app):  # type: ignore[arg-type]
            assert received_apps == [mock_app]
