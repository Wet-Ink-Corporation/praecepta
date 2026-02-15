"""Unit tests for praecepta.infra.observability.middleware."""

from __future__ import annotations

import pytest

from praecepta.foundation.application.contributions import MiddlewareContribution
from praecepta.infra.observability.middleware import (
    TraceContextMiddleware,
    contribution,
)


class TestContribution:
    @pytest.mark.unit
    def test_contribution_is_middleware_contribution(self) -> None:
        assert isinstance(contribution, MiddlewareContribution)

    @pytest.mark.unit
    def test_contribution_middleware_class(self) -> None:
        assert contribution.middleware_class is TraceContextMiddleware

    @pytest.mark.unit
    def test_contribution_priority(self) -> None:
        assert contribution.priority == 20


class TestTraceContextMiddleware:
    @pytest.mark.unit
    def test_middleware_class_exists(self) -> None:
        # TraceContextMiddleware should be importable and be a class
        assert isinstance(TraceContextMiddleware, type)
