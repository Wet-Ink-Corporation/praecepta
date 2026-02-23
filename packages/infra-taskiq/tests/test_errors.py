"""Tests for TaskIQ error hierarchy."""

from __future__ import annotations

import pytest

from praecepta.infra.taskiq.errors import (
    TaskIQBrokerError,
    TaskIQError,
    TaskIQResultError,
    TaskIQSerializationError,
)


@pytest.mark.unit
class TestTaskIQErrorHierarchy:
    def test_base_error_is_exception(self) -> None:
        assert issubclass(TaskIQError, Exception)

    def test_broker_error_is_taskiq_error(self) -> None:
        assert issubclass(TaskIQBrokerError, TaskIQError)

    def test_serialization_error_is_taskiq_error(self) -> None:
        assert issubclass(TaskIQSerializationError, TaskIQError)

    def test_result_error_is_taskiq_error(self) -> None:
        assert issubclass(TaskIQResultError, TaskIQError)

    def test_base_error_not_transient(self) -> None:
        assert TaskIQError.transient is False

    def test_broker_error_is_transient(self) -> None:
        assert TaskIQBrokerError.transient is True

    def test_serialization_error_not_transient(self) -> None:
        assert TaskIQSerializationError.transient is False

    def test_result_error_is_transient(self) -> None:
        assert TaskIQResultError.transient is True

    def test_catch_base_catches_subtypes(self) -> None:
        with pytest.raises(TaskIQError):
            raise TaskIQBrokerError("connection refused")
