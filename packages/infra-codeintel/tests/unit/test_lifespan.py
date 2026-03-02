"""Unit tests for lifespan contribution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from praecepta.infra.codeintel.lifespan import lifespan_contribution


@pytest.mark.unit
class TestLifespanContribution:
    def test_priority(self) -> None:
        assert lifespan_contribution.priority == 250

    def test_hook_is_callable(self) -> None:
        assert callable(lifespan_contribution.hook)

    @pytest.mark.asyncio
    async def test_startup_loads_indexes(self) -> None:
        # Mock the structural index .load() and semantic index
        with (
            patch(
                "praecepta.infra.codeintel.index.structural_index.NetworkXStructuralIndex"
            ) as mock_struct,
            patch(
                "praecepta.infra.codeintel.index.semantic_index.LanceDBSemanticIndex"
            ) as mock_sem,
        ):
            mock_struct_instance = MagicMock()
            mock_struct.return_value = mock_struct_instance
            mock_sem_instance = MagicMock()
            mock_sem.return_value = mock_sem_instance

            async with lifespan_contribution.hook(MagicMock()):
                mock_struct_instance.load.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_saves_indexes(self) -> None:
        with (
            patch(
                "praecepta.infra.codeintel.index.structural_index.NetworkXStructuralIndex"
            ) as mock_struct,
            patch(
                "praecepta.infra.codeintel.index.semantic_index.LanceDBSemanticIndex"
            ) as mock_sem,
        ):
            mock_struct_instance = MagicMock()
            mock_struct.return_value = mock_struct_instance
            mock_sem_instance = MagicMock()
            mock_sem.return_value = mock_sem_instance

            async with lifespan_contribution.hook(MagicMock()):
                pass
            # After context manager exits:
            mock_struct_instance.save.assert_called_once()
