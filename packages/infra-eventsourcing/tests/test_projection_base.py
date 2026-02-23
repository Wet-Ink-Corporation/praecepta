"""Tests for BaseProjection contract."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from praecepta.infra.eventsourcing.projections.base import BaseProjection
from praecepta.infra.eventsourcing.projections.rebuilder import ProjectionRebuilder
from praecepta.infra.eventsourcing.projections.runner import ProjectionRunner


@pytest.mark.unit
class TestBaseProjectionContract:
    """Tests for BaseProjection abstract contract."""

    def test_cannot_instantiate_without_clear_read_model(self) -> None:
        """BaseProjection requires clear_read_model() implementation."""
        # BaseProjection is abstract, so we verify it has the abstract method
        assert hasattr(BaseProjection, "clear_read_model")
        assert getattr(BaseProjection.clear_read_model, "__isabstractmethod__", False)

    def test_has_policy_method(self) -> None:
        assert hasattr(BaseProjection, "policy")

    def test_has_get_projection_name(self) -> None:
        assert hasattr(BaseProjection, "get_projection_name")

    def test_has_upstream_application_attribute(self) -> None:
        assert hasattr(BaseProjection, "upstream_application")

    def test_upstream_application_defaults_to_none(self) -> None:
        assert BaseProjection.upstream_application is None


@pytest.mark.unit
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
class TestProjectionRunner:
    """Tests for ProjectionRunner lifecycle (deprecated, use ProjectionPoller)."""

    def test_not_running_initially(self) -> None:
        runner = ProjectionRunner(
            projections=[],
            upstream_application=MagicMock,
        )
        assert not runner.is_running

    def test_emits_deprecation_warning(self) -> None:
        with pytest.warns(DeprecationWarning, match="ProjectionPoller"):
            ProjectionRunner(
                projections=[],
                upstream_application=MagicMock,
            )

    def test_get_raises_when_not_started(self) -> None:
        runner = ProjectionRunner(
            projections=[],
            upstream_application=MagicMock,
        )
        with pytest.raises(RuntimeError, match="not started"):
            runner.get(MagicMock)

    def test_stop_when_not_started_does_not_raise(self) -> None:
        runner = ProjectionRunner(
            projections=[],
            upstream_application=MagicMock,
        )
        # Should not raise
        runner.stop()

    @patch("praecepta.infra.eventsourcing.projections.runner.SingleThreadedRunner", create=True)
    @patch("praecepta.infra.eventsourcing.projections.runner.System", create=True)
    def test_start_sets_running(
        self, mock_system_cls: MagicMock, mock_runner_cls: MagicMock
    ) -> None:
        # We need to mock the imports inside start()
        with (
            patch(
                "praecepta.infra.eventsourcing.projections.runner.SingleThreadedRunner",
                create=True,
            ),
            patch(
                "praecepta.infra.eventsourcing.projections.runner.System",
                create=True,
            ),
        ):
            # Since start() imports from eventsourcing.system, we mock that
            mock_system = MagicMock()
            mock_runner = MagicMock()

            with patch.dict(
                "sys.modules",
                {
                    "eventsourcing.system": MagicMock(
                        System=lambda pipes: mock_system,
                        SingleThreadedRunner=lambda system, env: mock_runner,
                    )
                },
            ):
                runner = ProjectionRunner(
                    projections=[],
                    upstream_application=MagicMock,
                )
                runner.start()
                assert runner.is_running

    def test_start_twice_raises(self) -> None:
        runner = ProjectionRunner(
            projections=[],
            upstream_application=MagicMock,
        )
        runner._started = True  # Simulate already started
        with pytest.raises(RuntimeError, match="already started"):
            runner.start()


@pytest.mark.unit
class TestProjectionRebuilder:
    """Tests for ProjectionRebuilder workflow."""

    def test_rebuild_calls_clear_read_model(self) -> None:
        mock_projection = MagicMock()
        mock_projection.name = "TestProjection"

        mock_app = MagicMock()
        mock_app.recorder.delete_tracking_record = MagicMock()

        rebuilder = ProjectionRebuilder(upstream_app=mock_app)
        rebuilder.rebuild(mock_projection)

        mock_projection.clear_read_model.assert_called_once()

    def test_rebuild_resets_tracking_position(self) -> None:
        mock_projection = MagicMock()
        mock_projection.name = "TestProjection"

        mock_app = MagicMock()
        rebuilder = ProjectionRebuilder(upstream_app=mock_app)
        rebuilder.rebuild(mock_projection)

        mock_app.recorder.delete_tracking_record.assert_called_once_with("TestProjection")

    def test_rebuild_handles_missing_delete_tracking(self) -> None:
        """Rebuilder should warn if recorder doesn't support delete_tracking_record."""
        mock_projection = MagicMock()
        mock_projection.name = "TestProjection"

        mock_recorder = MagicMock(spec=[])  # No methods on recorder
        mock_app = MagicMock()
        mock_app.recorder = mock_recorder

        rebuilder = ProjectionRebuilder(upstream_app=mock_app)
        # Should not raise, just log warning
        rebuilder.rebuild(mock_projection)
