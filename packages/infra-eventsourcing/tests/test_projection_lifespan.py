"""Tests for projection poller auto-discovery lifespan hook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from praecepta.foundation.application import LifespanContribution
from praecepta.foundation.application.discovery import DiscoveredContribution
from praecepta.infra.eventsourcing.projection_lifespan import (
    GROUP_APPLICATIONS,
    GROUP_PROJECTIONS,
    _discover_applications,
    _discover_projections,
    projection_lifespan_contribution,
    projection_runner_lifespan,
)
from praecepta.infra.eventsourcing.projections.base import BaseProjection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contrib(name: str, group: str, value: object) -> DiscoveredContribution:
    return DiscoveredContribution(name=name, group=group, value=value)


class _StubProjection(BaseProjection):
    """Concrete BaseProjection subclass for testing."""

    def clear_read_model(self) -> None:
        pass


class _AnotherProjection(BaseProjection):
    """Another concrete BaseProjection subclass for testing."""

    def clear_read_model(self) -> None:
        pass


class _StubApplication:
    """Fake application class for testing."""


class _AnotherApplication:
    """Another fake application class for testing."""


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
# Tests: _discover_applications
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDiscoverApplications:
    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_returns_application_classes(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = [
            _make_contrib("a1", GROUP_APPLICATIONS, _StubApplication),
        ]
        result = _discover_applications()
        assert result == [_StubApplication]
        mock_discover.assert_called_once_with(GROUP_APPLICATIONS)

    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_filters_non_class(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = [
            _make_contrib("bad", GROUP_APPLICATIONS, "not_a_class"),
        ]
        result = _discover_applications()
        assert result == []

    @patch("praecepta.infra.eventsourcing.projection_lifespan.discover")
    def test_empty_entry_points(self, mock_discover: MagicMock) -> None:
        mock_discover.return_value = []
        result = _discover_applications()
        assert result == []


# ---------------------------------------------------------------------------
# Tests: projection_runner_lifespan (async context manager)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionRunnerLifespan:
    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_no_projections_is_noop(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
    ) -> None:
        """When no projections found, yield without starting pollers."""
        mock_proj.return_value = []
        async with projection_runner_lifespan(MagicMock()):
            pass
        mock_apps.assert_not_called()

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_no_applications_is_noop(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
    ) -> None:
        """Projections exist but no applications -> yield without pollers."""
        mock_proj.return_value = [_StubProjection]
        mock_apps.return_value = []
        async with projection_runner_lifespan(MagicMock()):
            pass

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.ProjectionPoller")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_one_app_one_projection_starts_and_stops(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
        mock_poller_cls: MagicMock,
    ) -> None:
        """Single app + single projection -> one poller started then stopped."""
        mock_proj.return_value = [_StubProjection]
        mock_apps.return_value = [_StubApplication]
        mock_poller = MagicMock()
        mock_poller_cls.return_value = mock_poller

        async with projection_runner_lifespan(MagicMock()):
            mock_poller_cls.assert_called_once_with(
                projections=[_StubProjection],
                upstream_application=_StubApplication,
            )
            mock_poller.start.assert_called_once()
            mock_poller.stop.assert_not_called()

        mock_poller.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.ProjectionPoller")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_multiple_apps_creates_multiple_pollers(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
        mock_poller_cls: MagicMock,
    ) -> None:
        """Multiple applications -> one poller per application."""
        mock_proj.return_value = [_StubProjection, _AnotherProjection]
        mock_apps.return_value = [_StubApplication, _AnotherApplication]
        mock_pollers = [MagicMock(), MagicMock()]
        mock_poller_cls.side_effect = mock_pollers

        async with projection_runner_lifespan(MagicMock()):
            assert mock_poller_cls.call_count == 2
            for poller in mock_pollers:
                poller.start.assert_called_once()

        for poller in mock_pollers:
            poller.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.ProjectionPoller")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_each_poller_receives_all_projections(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
        mock_poller_cls: MagicMock,
    ) -> None:
        """Each poller receives the complete list of projections."""
        mock_proj.return_value = [_StubProjection, _AnotherProjection]
        mock_apps.return_value = [_StubApplication, _AnotherApplication]
        mock_poller_cls.return_value = MagicMock()

        async with projection_runner_lifespan(MagicMock()):
            calls = mock_poller_cls.call_args_list
            assert calls[0] == (
                (),
                {
                    "projections": [_StubProjection, _AnotherProjection],
                    "upstream_application": _StubApplication,
                },
            )
            assert calls[1] == (
                (),
                {
                    "projections": [_StubProjection, _AnotherProjection],
                    "upstream_application": _AnotherApplication,
                },
            )

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.ProjectionPoller")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_start_failure_propagates(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
        mock_poller_cls: MagicMock,
    ) -> None:
        """If poller.start() raises, the exception propagates."""
        mock_proj.return_value = [_StubProjection]
        mock_apps.return_value = [_StubApplication]
        mock_poller = MagicMock()
        mock_poller.start.side_effect = RuntimeError("start failed")
        mock_poller_cls.return_value = mock_poller

        with pytest.raises(RuntimeError, match="start failed"):
            async with projection_runner_lifespan(MagicMock()):
                pass  # pragma: no cover

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.ProjectionPoller")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_stop_called_on_exception_during_yield(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
        mock_poller_cls: MagicMock,
    ) -> None:
        """Pollers are stopped even if an exception occurs during yield."""
        mock_proj.return_value = [_StubProjection]
        mock_apps.return_value = [_StubApplication]
        mock_poller = MagicMock()
        mock_poller_cls.return_value = mock_poller

        with pytest.raises(ValueError, match="app error"):
            async with projection_runner_lifespan(MagicMock()):
                raise ValueError("app error")

        mock_poller.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("praecepta.infra.eventsourcing.projection_lifespan.ProjectionPoller")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_applications")
    @patch("praecepta.infra.eventsourcing.projection_lifespan._discover_projections")
    async def test_partial_start_failure_stops_already_started(
        self,
        mock_proj: MagicMock,
        mock_apps: MagicMock,
        mock_poller_cls: MagicMock,
    ) -> None:
        """If second poller.start() fails, first poller is still stopped."""
        mock_proj.return_value = [_StubProjection]
        mock_apps.return_value = [_StubApplication, _AnotherApplication]

        poller_ok = MagicMock()
        poller_fail = MagicMock()
        poller_fail.start.side_effect = RuntimeError("db connection failed")
        mock_poller_cls.side_effect = [poller_ok, poller_fail]

        with pytest.raises(RuntimeError, match="db connection failed"):
            async with projection_runner_lifespan(MagicMock()):
                pass  # pragma: no cover

        poller_ok.stop.assert_called_once()
        poller_fail.stop.assert_not_called()
