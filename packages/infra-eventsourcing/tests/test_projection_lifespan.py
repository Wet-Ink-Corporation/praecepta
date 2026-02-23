"""Tests for projection runner auto-discovery lifespan hook."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from praecepta.foundation.application import LifespanContribution
from praecepta.foundation.application.discovery import DiscoveredContribution
from praecepta.infra.eventsourcing.projection_lifespan import (
    GROUP_PROJECTIONS,
    _discover_projections,
    _group_projections_by_application,
    projection_lifespan_contribution,
    projection_runner_lifespan,
)
from praecepta.infra.eventsourcing.projections.base import BaseProjection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contrib(name: str, group: str, value: object) -> DiscoveredContribution:
    return DiscoveredContribution(name=name, group=group, value=value)


class _StubApplication:
    """Fake application class for testing."""

    __name__ = "_StubApplication"


class _AnotherApplication:
    """Another fake application class for testing."""

    __name__ = "_AnotherApplication"


class _StubProjection(BaseProjection):
    """Concrete BaseProjection subclass for testing (with upstream)."""

    upstream_application: ClassVar[type[Any]] = _StubApplication  # type: ignore[assignment]

    def clear_read_model(self) -> None:
        pass


class _AnotherProjection(BaseProjection):
    """Another concrete BaseProjection subclass for testing (with upstream)."""

    upstream_application: ClassVar[type[Any]] = _AnotherApplication  # type: ignore[assignment]

    def clear_read_model(self) -> None:
        pass


class _OrphanProjection(BaseProjection):
    """Projection without upstream_application set."""

    def clear_read_model(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests: module-level contribution instance
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionLifespanContribution:
    def test_is_lifespan_contribution(self) -> None:
        assert isinstance(projection_lifespan_contribution, LifespanContribution)

    def test_priority_is_200(self) -> None:
        assert projection_lifespan_contribution.priority == 200

    def test_priority_after_event_store(self) -> None:
        from praecepta.infra.eventsourcing.lifespan import lifespan_contribution

        assert projection_lifespan_contribution.priority > lifespan_contribution.priority

    def test_hook_is_callable(self) -> None:
        assert callable(projection_lifespan_contribution.hook)


# ---------------------------------------------------------------------------
# Tests: _discover_projections
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDiscoverProjections:
    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_returns_base_projection_subclasses(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = [
            _make_contrib("p1", GROUP_PROJECTIONS, _StubProjection),
        ]
        result = _discover_projections()
        assert result == [_StubProjection]
        mock_discover.assert_called_once_with(GROUP_PROJECTIONS)

    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_filters_non_class_value(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = [
            _make_contrib("bad", GROUP_PROJECTIONS, "not_a_class"),
        ]
        result = _discover_projections()
        assert result == []

    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_filters_wrong_base_class(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = [
            _make_contrib("wrong", GROUP_PROJECTIONS, _StubApplication),
        ]
        result = _discover_projections()
        assert result == []

    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_empty_entry_points(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = []
        result = _discover_projections()
        assert result == []

    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_multiple_projections(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = [
            _make_contrib("p1", GROUP_PROJECTIONS, _StubProjection),
            _make_contrib("p2", GROUP_PROJECTIONS, _AnotherProjection),
        ]
        result = _discover_projections()
        assert result == [_StubProjection, _AnotherProjection]


# ---------------------------------------------------------------------------
# Tests: _group_projections_by_application
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGroupProjectionsByApplication:
    def test_groups_by_upstream_application(self) -> None:
        result = _group_projections_by_application([_StubProjection, _AnotherProjection])
        assert result == {
            _StubApplication: [_StubProjection],
            _AnotherApplication: [_AnotherProjection],
        }

    def test_multiple_projections_same_app(self) -> None:
        class _SecondStubProjection(BaseProjection):
            upstream_application: ClassVar[type[Any]] = _StubApplication  # type: ignore[assignment]

            def clear_read_model(self) -> None:
                pass

        result = _group_projections_by_application([_StubProjection, _SecondStubProjection])
        assert result == {
            _StubApplication: [_StubProjection, _SecondStubProjection],
        }

    def test_skips_projections_without_upstream(self) -> None:
        result = _group_projections_by_application([_OrphanProjection])
        assert result == {}

    def test_empty_input(self) -> None:
        result = _group_projections_by_application([])
        assert result == {}

    def test_mixed_valid_and_orphan(self) -> None:
        result = _group_projections_by_application([_StubProjection, _OrphanProjection])
        assert result == {
            _StubApplication: [_StubProjection],
        }


# ---------------------------------------------------------------------------
# Tests: projection_runner_lifespan (async context manager)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionRunnerLifespan:
    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_no_projections_is_noop(
        self,
        mock_proj: MagicMock,
    ) -> None:
        """When no projections found, yield without starting runners."""
        mock_proj.return_value = []
        async with projection_runner_lifespan(MagicMock()):
            pass

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_no_grouped_projections_is_noop(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
    ) -> None:
        """Projections exist but none declare upstream_application -> noop."""
        mock_proj.return_value = [_OrphanProjection]
        mock_group.return_value = {}
        async with projection_runner_lifespan(MagicMock()):
            pass

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.SubscriptionProjectionRunner")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_one_app_one_projection_starts_and_stops(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
        mock_runner_cls: MagicMock,
    ) -> None:
        """Single app + single projection -> one runner started then stopped."""
        mock_proj.return_value = [_StubProjection]
        mock_group.return_value = {_StubApplication: [_StubProjection]}
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        async with projection_runner_lifespan(MagicMock()):
            mock_runner_cls.assert_called_once_with(
                projections=[_StubProjection],
                upstream_application=_StubApplication,
            )
            mock_runner.start.assert_called_once()
            mock_runner.stop.assert_not_called()

        mock_runner.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.SubscriptionProjectionRunner")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_multiple_apps_creates_multiple_runners(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
        mock_runner_cls: MagicMock,
    ) -> None:
        """Multiple applications -> one runner per application."""
        mock_proj.return_value = [_StubProjection, _AnotherProjection]
        mock_group.return_value = {
            _StubApplication: [_StubProjection],
            _AnotherApplication: [_AnotherProjection],
        }
        mock_runners = [MagicMock(), MagicMock()]
        mock_runner_cls.side_effect = mock_runners

        async with projection_runner_lifespan(MagicMock()):
            assert mock_runner_cls.call_count == 2
            for runner in mock_runners:
                runner.start.assert_called_once()

        for runner in mock_runners:
            runner.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.SubscriptionProjectionRunner")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_projections_grouped_by_upstream_app(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
        mock_runner_cls: MagicMock,
    ) -> None:
        """Each runner receives only its application's projections."""
        mock_proj.return_value = [_StubProjection, _AnotherProjection]
        mock_group.return_value = {
            _StubApplication: [_StubProjection],
            _AnotherApplication: [_AnotherProjection],
        }
        mock_runner_cls.return_value = MagicMock()

        async with projection_runner_lifespan(MagicMock()):
            calls = mock_runner_cls.call_args_list
            assert calls[0] == (
                (),
                {
                    "projections": [_StubProjection],
                    "upstream_application": _StubApplication,
                },
            )
            assert calls[1] == (
                (),
                {
                    "projections": [_AnotherProjection],
                    "upstream_application": _AnotherApplication,
                },
            )

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.SubscriptionProjectionRunner")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_start_failure_propagates(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
        mock_runner_cls: MagicMock,
    ) -> None:
        """If runner.start() raises, the exception propagates."""
        mock_proj.return_value = [_StubProjection]
        mock_group.return_value = {_StubApplication: [_StubProjection]}
        mock_runner = MagicMock()
        mock_runner.start.side_effect = RuntimeError("start failed")
        mock_runner_cls.return_value = mock_runner

        with pytest.raises(RuntimeError, match="start failed"):
            async with projection_runner_lifespan(MagicMock()):
                pass  # pragma: no cover

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.SubscriptionProjectionRunner")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_stop_called_on_exception_during_yield(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
        mock_runner_cls: MagicMock,
    ) -> None:
        """Runners are stopped even if an exception occurs during yield."""
        mock_proj.return_value = [_StubProjection]
        mock_group.return_value = {_StubApplication: [_StubProjection]}
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        with pytest.raises(ValueError, match="app error"):
            async with projection_runner_lifespan(MagicMock()):
                raise ValueError("app error")

        mock_runner.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"MAX_PROJECTION_RUNNERS": "1"})
    @patch("praecepta.infra.eventsourcing.projection_lifespan.SubscriptionProjectionRunner")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_max_projection_runners_caps_projections(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
        mock_runner_cls: MagicMock,
    ) -> None:
        """When MAX_PROJECTION_RUNNERS=1, only one projection runner starts."""
        mock_proj.return_value = [_StubProjection, _AnotherProjection]
        mock_group.return_value = {
            _StubApplication: [_StubProjection],
            _AnotherApplication: [_AnotherProjection],
        }
        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        async with projection_runner_lifespan(MagicMock()):
            # Only 1 runner should be created due to cap
            assert mock_runner_cls.call_count == 1

        mock_runner.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.SubscriptionProjectionRunner")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._group_projections_by_application")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_partial_start_failure_stops_already_started(
        self,
        mock_proj: MagicMock,
        mock_group: MagicMock,
        mock_runner_cls: MagicMock,
    ) -> None:
        """If second runner.start() fails, first runner is still stopped."""
        mock_proj.return_value = [_StubProjection, _AnotherProjection]
        mock_group.return_value = {
            _StubApplication: [_StubProjection],
            _AnotherApplication: [_AnotherProjection],
        }

        runner_ok = MagicMock()
        runner_fail = MagicMock()
        runner_fail.start.side_effect = RuntimeError("db connection failed")
        mock_runner_cls.side_effect = [runner_ok, runner_fail]

        with pytest.raises(RuntimeError, match="db connection failed"):
            async with projection_runner_lifespan(MagicMock()):
                pass  # pragma: no cover

        runner_ok.stop.assert_called_once()
        runner_fail.stop.assert_not_called()
