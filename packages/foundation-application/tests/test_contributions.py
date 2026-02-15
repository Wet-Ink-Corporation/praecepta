"""Unit tests for praecepta.foundation.application.contributions."""

from __future__ import annotations

import pytest

from praecepta.foundation.application.contributions import (
    ErrorHandlerContribution,
    LifespanContribution,
    MiddlewareContribution,
)


class TestMiddlewareContribution:
    @pytest.mark.unit
    def test_default_priority_is_500(self) -> None:
        mc = MiddlewareContribution(middleware_class=type)
        assert mc.priority == 500

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
