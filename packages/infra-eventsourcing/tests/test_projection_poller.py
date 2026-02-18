"""Tests for ProjectionPoller polling-based projection runner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from praecepta.infra.eventsourcing.projections.poller import ProjectionPoller
from praecepta.infra.eventsourcing.settings import ProjectionPollingSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeApp:
    """Stub upstream application class with a name attribute."""

    name = "FakeApp"


def _make_settings(**overrides: object) -> ProjectionPollingSettings:
    """Create polling settings with optional overrides."""
    defaults: dict[str, object] = {
        "poll_interval": 0.1,
        "poll_timeout": 2.0,
        "poll_enabled": True,
    }
    defaults.update(overrides)
    return ProjectionPollingSettings(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: ProjectionPollingSettings
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionPollingSettings:
    def test_default_values(self) -> None:
        settings = ProjectionPollingSettings()
        assert settings.poll_interval == 1.0
        assert settings.poll_timeout == 10.0
        assert settings.poll_enabled is True

    def test_custom_interval(self) -> None:
        settings = ProjectionPollingSettings(poll_interval=5.0)
        assert settings.poll_interval == 5.0

    def test_interval_lower_bound(self) -> None:
        with pytest.raises(ValueError):
            ProjectionPollingSettings(poll_interval=0.05)

    def test_interval_upper_bound(self) -> None:
        with pytest.raises(ValueError):
            ProjectionPollingSettings(poll_interval=61.0)

    def test_timeout_lower_bound(self) -> None:
        with pytest.raises(ValueError):
            ProjectionPollingSettings(poll_timeout=0.5)

    def test_timeout_upper_bound(self) -> None:
        with pytest.raises(ValueError):
            ProjectionPollingSettings(poll_timeout=121.0)


# ---------------------------------------------------------------------------
# Tests: ProjectionPoller lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionPollerLifecycle:
    def test_not_running_initially(self) -> None:
        poller = ProjectionPoller(
            projections=[],
            upstream_application=MagicMock,
            settings=_make_settings(),
        )
        assert not poller.is_running

    def test_get_raises_when_not_started(self) -> None:
        poller = ProjectionPoller(
            projections=[],
            upstream_application=MagicMock,
            settings=_make_settings(),
        )
        with pytest.raises(RuntimeError, match="not started"):
            poller.get(MagicMock)

    def test_stop_when_not_started_does_not_raise(self) -> None:
        poller = ProjectionPoller(
            projections=[],
            upstream_application=MagicMock,
            settings=_make_settings(),
        )
        # Should not raise
        poller.stop()

    def test_start_twice_raises(self) -> None:
        poller = ProjectionPoller(
            projections=[],
            upstream_application=MagicMock,
            settings=_make_settings(),
        )
        poller._started = True  # Simulate already started
        with pytest.raises(RuntimeError, match="already started"):
            poller.start()


# ---------------------------------------------------------------------------
# Tests: ProjectionPoller start/stop with mocked System
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionPollerStartStop:
    def test_start_creates_runner_and_thread(self) -> None:
        mock_system = MagicMock()
        mock_runner = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "eventsourcing.system": MagicMock(
                    System=lambda pipes: mock_system,
                    SingleThreadedRunner=lambda system, env: mock_runner,
                ),
            },
        ):
            poller = ProjectionPoller(
                projections=[],
                upstream_application=_FakeApp,
                settings=_make_settings(),
            )
            poller.start()

            assert poller.is_running
            assert poller._poll_thread is not None
            assert poller._poll_thread.is_alive()

            mock_runner.start.assert_called_once()

            poller.stop()

            assert not poller.is_running
            mock_runner.stop.assert_called_once()

    def test_stop_sets_stop_event_and_joins_thread(self) -> None:
        mock_system = MagicMock()
        mock_runner = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "eventsourcing.system": MagicMock(
                    System=lambda pipes: mock_system,
                    SingleThreadedRunner=lambda system, env: mock_runner,
                ),
            },
        ):
            poller = ProjectionPoller(
                projections=[],
                upstream_application=_FakeApp,
                settings=_make_settings(),
            )
            poller.start()

            assert not poller._stop_event.is_set()
            poller.stop()
            assert poller._stop_event.is_set()

    def test_context_manager_starts_and_stops(self) -> None:
        mock_system = MagicMock()
        mock_runner = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "eventsourcing.system": MagicMock(
                    System=lambda pipes: mock_system,
                    SingleThreadedRunner=lambda system, env: mock_runner,
                ),
            },
        ):
            poller = ProjectionPoller(
                projections=[],
                upstream_application=_FakeApp,
                settings=_make_settings(),
            )

            with poller:
                assert poller.is_running
                mock_runner.start.assert_called_once()

            assert not poller.is_running
            mock_runner.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: ProjectionPoller poll loop
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionPollerPollLoop:
    def test_poll_loop_calls_pull_and_process(self) -> None:
        """Poll loop should call pull_and_process on each projection."""

        mock_follower = MagicMock()
        mock_runner = MagicMock()
        mock_runner.get.return_value = mock_follower

        projection_cls = MagicMock()
        projection_cls.__name__ = "TestProjection"

        poller = ProjectionPoller(
            projections=[projection_cls],
            upstream_application=_FakeApp,
            settings=_make_settings(),
        )
        poller._runner = mock_runner
        poller._started = True

        # Run one iteration of the poll loop, then stop
        call_count = 0
        original_wait = poller._stop_event.wait

        def counted_wait(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller._stop_event.set()
            return original_wait(timeout)

        poller._stop_event.wait = counted_wait  # type: ignore[assignment]

        # Run _poll_loop directly (not in a thread, for deterministic testing)
        poller._poll_loop()

        mock_runner.get.assert_called_with(projection_cls)
        mock_follower.pull_and_process.assert_called_with("FakeApp")

    def test_poll_loop_catches_exceptions(self) -> None:
        """Exceptions in pull_and_process should be logged, not crash the loop."""

        mock_follower = MagicMock()
        mock_follower.pull_and_process.side_effect = RuntimeError("db error")
        mock_runner = MagicMock()
        mock_runner.get.return_value = mock_follower

        projection_cls = MagicMock()
        projection_cls.__name__ = "TestProjection"

        poller = ProjectionPoller(
            projections=[projection_cls],
            upstream_application=_FakeApp,
            settings=_make_settings(),
        )
        poller._runner = mock_runner
        poller._started = True

        call_count = 0
        original_wait = poller._stop_event.wait

        def counted_wait(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                poller._stop_event.set()
            return original_wait(timeout)

        poller._stop_event.wait = counted_wait  # type: ignore[assignment]

        # Should not raise — exceptions are caught and logged
        poller._poll_loop()

        # pull_and_process was still called (loop continued after error)
        assert mock_follower.pull_and_process.call_count >= 1

    def test_poll_loop_respects_stop_event_between_projections(self) -> None:
        """Stop event should be checked between processing projections."""
        proj1 = MagicMock()
        proj1.__name__ = "Proj1"
        proj2 = MagicMock()
        proj2.__name__ = "Proj2"

        call_order: list[str] = []
        mock_runner = MagicMock()

        def get_follower(cls: type) -> MagicMock:
            follower = MagicMock()

            def side_effect(leader: str) -> None:
                call_order.append(cls.__name__)
                # Stop after first projection processes
                if cls.__name__ == "Proj1":
                    poller._stop_event.set()

            follower.pull_and_process.side_effect = side_effect
            return follower

        mock_runner.get.side_effect = get_follower

        poller = ProjectionPoller(
            projections=[proj1, proj2],
            upstream_application=_FakeApp,
            settings=_make_settings(),
        )
        poller._runner = mock_runner
        poller._started = True

        poller._poll_loop()

        # Only proj1 should have been processed before stop
        assert call_order == ["Proj1"]

    def test_get_delegates_to_runner(self) -> None:
        mock_runner = MagicMock()
        mock_runner.get.return_value = "app_instance"

        poller = ProjectionPoller(
            projections=[],
            upstream_application=MagicMock,
            settings=_make_settings(),
        )
        poller._runner = mock_runner
        poller._started = True

        result = poller.get(MagicMock)
        assert result == "app_instance"


# ---------------------------------------------------------------------------
# Tests: ProjectionPoller with multiple projections
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProjectionPollerMultipleProjections:
    def test_poll_loop_processes_all_projections(self) -> None:
        """All projections should be polled in each cycle."""
        proj1 = MagicMock()
        proj1.__name__ = "Proj1"
        proj2 = MagicMock()
        proj2.__name__ = "Proj2"

        followers: dict[str, MagicMock] = {}

        def get_follower(cls: type) -> MagicMock:
            if cls.__name__ not in followers:
                followers[cls.__name__] = MagicMock()
            return followers[cls.__name__]

        mock_runner = MagicMock()
        mock_runner.get.side_effect = get_follower

        poller = ProjectionPoller(
            projections=[proj1, proj2],
            upstream_application=_FakeApp,
            settings=_make_settings(),
        )
        poller._runner = mock_runner
        poller._started = True

        call_count = 0
        original_wait = poller._stop_event.wait

        def counted_wait(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                poller._stop_event.set()
            return original_wait(timeout)

        poller._stop_event.wait = counted_wait  # type: ignore[assignment]

        poller._poll_loop()

        # Both projections should have been processed
        assert "Proj1" in followers
        assert "Proj2" in followers
        followers["Proj1"].pull_and_process.assert_called_with("FakeApp")
        followers["Proj2"].pull_and_process.assert_called_with("FakeApp")
