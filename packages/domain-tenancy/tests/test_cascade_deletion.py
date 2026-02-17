"""Unit tests for CascadeDeletionService."""

from __future__ import annotations

from uuid import uuid4

import pytest

from praecepta.domain.tenancy.infrastructure.cascade_deletion import (
    CascadeDeletionResult,
    CascadeDeletionService,
)


@pytest.mark.unit
class TestCascadeDeletionResult:
    """CascadeDeletionResult data class."""

    def test_defaults(self) -> None:
        result = CascadeDeletionResult()
        assert result.projections_deleted == 0
        assert result.slug_released is False
        assert result.categories_processed == []


@pytest.mark.unit
class TestCascadeDeletionService:
    """CascadeDeletionService operations."""

    def test_delete_tenant_data_returns_result(self) -> None:
        service = CascadeDeletionService()
        result = service.delete_tenant_data(
            tenant_slug="acme-corp",
            aggregate_id=uuid4(),
        )
        assert isinstance(result, CascadeDeletionResult)

    def test_marks_slug_released(self) -> None:
        service = CascadeDeletionService()
        result = service.delete_tenant_data(
            tenant_slug="acme-corp",
            aggregate_id=uuid4(),
        )
        assert result.slug_released is True

    def test_slug_reservation_in_categories(self) -> None:
        service = CascadeDeletionService()
        result = service.delete_tenant_data(
            tenant_slug="acme-corp",
            aggregate_id=uuid4(),
        )
        assert "slug_reservation" in result.categories_processed
