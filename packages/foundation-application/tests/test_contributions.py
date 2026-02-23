"""Unit tests for praecepta.foundation.application.contributions."""

from __future__ import annotations

import pytest

from praecepta.foundation.application.contributions import (
    LIFESPAN_PRIORITY_EVENTSTORE,
    LIFESPAN_PRIORITY_OBSERVABILITY,
    LIFESPAN_PRIORITY_PERSISTENCE,
    LIFESPAN_PRIORITY_PROJECTIONS,
    LIFESPAN_PRIORITY_TASKIQ,
    ErrorHandlerContribution,
    LifespanContribution,
    MiddlewareContribution,
)


class TestMiddlewareContribution:
    @pytest.mark.unit
    def test_default_priority_is_400(self) -> None:
        mc = MiddlewareContribution(middleware_class=type)
        assert mc.priority == 400

    @pytest.mark.unit
    def test_kwargs_defaults_to_empty_dict(self) -> None:
        mc = MiddlewareContribution(middleware_class=type)
        assert mc.kwargs == {}

    @pytest.mark.unit
    def test_custom_priority_and_kwargs(self) -> None:
        mc = MiddlewareContribution(
            middleware_class=type,
            priority=100,
            kwargs={"key": "value"},
        )
        assert mc.priority == 100
        assert mc.kwargs == {"key": "value"}

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        mc = MiddlewareContribution(middleware_class=type)
        with pytest.raises(AttributeError):
            mc.priority = 10  # type: ignore[misc]

    @pytest.mark.unit
    def test_priority_below_min_raises(self) -> None:
        with pytest.raises(ValueError, match="priority must be between"):
            MiddlewareContribution(middleware_class=type, priority=-1)

    @pytest.mark.unit
    def test_priority_above_max_raises(self) -> None:
        with pytest.raises(ValueError, match="priority must be between"):
            MiddlewareContribution(middleware_class=type, priority=500)

    @pytest.mark.unit
    def test_priority_at_boundaries_ok(self) -> None:
        mc_min = MiddlewareContribution(middleware_class=type, priority=0)
        assert mc_min.priority == 0
        mc_max = MiddlewareContribution(middleware_class=type, priority=499)
        assert mc_max.priority == 499


class TestErrorHandlerContribution:
    @pytest.mark.unit
    def test_stores_exception_class_and_handler(self) -> None:
        async def handler(request: object, exc: Exception) -> object:
            return None

        eh = ErrorHandlerContribution(exception_class=ValueError, handler=handler)
        assert eh.exception_class is ValueError
        assert eh.handler is handler

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        eh = ErrorHandlerContribution(exception_class=ValueError, handler=lambda r, e: None)
        with pytest.raises(AttributeError):
            eh.exception_class = TypeError  # type: ignore[misc]


class TestLifespanContribution:
    @pytest.mark.unit
    def test_default_priority_is_500(self) -> None:
        lc = LifespanContribution(hook=lambda app: None)
        assert lc.priority == 500

    @pytest.mark.unit
    def test_custom_priority(self) -> None:
        lc = LifespanContribution(hook=lambda app: None, priority=100)
        assert lc.priority == 100

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        lc = LifespanContribution(hook=lambda app: None)
        with pytest.raises(AttributeError):
            lc.priority = 10  # type: ignore[misc]


class TestLifespanPriorityConstants:
    @pytest.mark.unit
    def test_priority_ordering(self) -> None:
        assert (
            LIFESPAN_PRIORITY_OBSERVABILITY
            < LIFESPAN_PRIORITY_PERSISTENCE
            < LIFESPAN_PRIORITY_EVENTSTORE
            < LIFESPAN_PRIORITY_TASKIQ
            < LIFESPAN_PRIORITY_PROJECTIONS
        )

    @pytest.mark.unit
    def test_known_values(self) -> None:
        assert LIFESPAN_PRIORITY_OBSERVABILITY == 50
        assert LIFESPAN_PRIORITY_PERSISTENCE == 75
        assert LIFESPAN_PRIORITY_EVENTSTORE == 100
        assert LIFESPAN_PRIORITY_TASKIQ == 150
        assert LIFESPAN_PRIORITY_PROJECTIONS == 200
