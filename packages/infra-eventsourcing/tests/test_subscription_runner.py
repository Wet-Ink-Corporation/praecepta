"""Tests for SubscriptionProjectionRunner lifecycle management."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from praecepta.infra.eventsourcing.projections.base import BaseProjection
from praecepta.infra.eventsourcing.projections.subscription_runner import (
    SubscriptionProjectionRunner,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeApp:
    """Stub upstream application class."""

    __name__ = "FakeApp"


class _StubProjection(BaseProjection):
    """Concrete BaseProjection for testing."""

    upstream_application: ClassVar[type[Any]] = _FakeApp  # type: ignore[assignment]

    def clear_read_model(self) -> None:
        pass


class _AnotherProjection(BaseProjection):
    """Another projection for testing."""

    upstream_application: ClassVar[type[Any]] = _FakeApp  # type: ignore[assignment]

    def clear_read_model(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests: Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSubscriptionProjectionRunnerLifecycle:
    def test_not_running_initially(self) -> None:
        runner = SubscriptionProjectionRunner(
            projections=[],
            upstream_application=_FakeApp,
        )
        assert not runner.is_running

    def test_start_twice_raises(self) -> None:
        runner = SubscriptionProjectionRunner(
            projections=[],
            upstream_application=_FakeApp,
        )
        runner._started = True
        with pytest.raises(RuntimeError, match="already started"):
            runner.start()

    def test_stop_when_not_started_does_not_raise(self) -> None:
        runner = SubscriptionProjectionRunner(
            projections=[],
            upstream_application=_FakeApp,
        )
        runner.stop()  # Should not raise

    @patch("eventsourcing.projection.EventSourcedProjectionRunner")
    def test_start_creates_runner_per_projection(self, mock_es_runner_cls: MagicMock) -> None:
        """Each projection gets its own EventSourcedProjectionRunner."""
        mock_runner1 = MagicMock()
        mock_runner2 = MagicMock()
        mock_es_runner_cls.side_effect = [mock_runner1, mock_runner2]

        runner = SubscriptionProjectionRunner(
            projections=[_StubProjection, _AnotherProjection],
            upstream_application=_FakeApp,
        )
        runner.start()

        assert runner.is_running
        assert mock_es_runner_cls.call_count == 2
        mock_es_runner_cls.assert_any_call(
            application_class=_FakeApp,
            projection_class=_StubProjection,
            env=None,
        )
        mock_es_runner_cls.assert_any_call(
            application_class=_FakeApp,
            projection_class=_AnotherProjection,
            env=None,
        )
        mock_runner1.__enter__.assert_called_once()
        mock_runner2.__enter__.assert_called_once()

    @patch("eventsourcing.projection.EventSourcedProjectionRunner")
    def test_stop_exits_runners_in_reverse_order(self, mock_es_runner_cls: MagicMock) -> None:
        """Runners are stopped in reverse order of creation."""
        mock_runner1 = MagicMock()
        mock_runner1.projection = MagicMock()
        type(mock_runner1.projection).__name__ = "Proj1"
        mock_runner2 = MagicMock()
        mock_runner2.projection = MagicMock()
        type(mock_runner2.projection).__name__ = "Proj2"
        mock_es_runner_cls.side_effect = [mock_runner1, mock_runner2]

        runner = SubscriptionProjectionRunner(
            projections=[_StubProjection, _AnotherProjection],
            upstream_application=_FakeApp,
        )
        runner.start()
        runner.stop()

        assert not runner.is_running
        # Verify reverse order: runner2 stopped before runner1
        exit_calls = [mock_runner2.__exit__, mock_runner1.__exit__]
        for exit_mock in exit_calls:
            exit_mock.assert_called_once_with(None, None, None)

    @patch("eventsourcing.projection.EventSourcedProjectionRunner")
    def test_context_manager(self, mock_es_runner_cls: MagicMock) -> None:
        """Context manager starts on enter, stops on exit."""
        mock_es_runner = MagicMock()
        mock_es_runner_cls.return_value = mock_es_runner

        runner = SubscriptionProjectionRunner(
            projections=[_StubProjection],
            upstream_application=_FakeApp,
        )

        with runner:
            assert runner.is_running
            mock_es_runner.__enter__.assert_called_once()

        assert not runner.is_running
        mock_es_runner.__exit__.assert_called_once()

    @patch("eventsourcing.projection.EventSourcedProjectionRunner")
    def test_stop_handles_runner_exit_error(self, mock_es_runner_cls: MagicMock) -> None:
        """If a runner's __exit__ raises, other runners are still stopped."""
        mock_runner1 = MagicMock()
        mock_runner1.projection = MagicMock()
        type(mock_runner1.projection).__name__ = "Proj1"
        mock_runner2 = MagicMock()
        mock_runner2.projection = MagicMock()
        type(mock_runner2.projection).__name__ = "Proj2"
        mock_runner2.__exit__.side_effect = RuntimeError("cleanup failed")
        mock_es_runner_cls.side_effect = [mock_runner1, mock_runner2]

        runner = SubscriptionProjectionRunner(
            projections=[_StubProjection, _AnotherProjection],
            upstream_application=_FakeApp,
        )
        runner.start()
        # Should not raise despite runner2 error
        runner.stop()

        assert not runner.is_running
        # runner1 still stopped despite runner2 error
        mock_runner1.__exit__.assert_called_once()

    @patch("eventsourcing.projection.EventSourcedProjectionRunner")
    def test_env_passed_through(self, mock_es_runner_cls: MagicMock) -> None:
        """Environment variables are passed to each EventSourcedProjectionRunner."""
        mock_es_runner_cls.return_value = MagicMock()
        env = {"PERSISTENCE_MODULE": "eventsourcing.postgres"}

        runner = SubscriptionProjectionRunner(
            projections=[_StubProjection],
            upstream_application=_FakeApp,
            env=env,
        )
        runner.start()

        mock_es_runner_cls.assert_called_once_with(
            application_class=_FakeApp,
            projection_class=_StubProjection,
            env=env,
        )

    @patch("eventsourcing.projection.EventSourcedProjectionRunner")
    def test_empty_projections_list(self, mock_es_runner_cls: MagicMock) -> None:
        """Empty projections list starts and stops without error."""
        runner = SubscriptionProjectionRunner(
            projections=[],
            upstream_application=_FakeApp,
        )
        runner.start()
        assert runner.is_running
        mock_es_runner_cls.assert_not_called()

        runner.stop()
        assert not runner.is_running
