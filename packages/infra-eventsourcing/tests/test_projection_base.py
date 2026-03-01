"""Tests for BaseProjection contract."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from praecepta.infra.eventsourcing.projections.base import BaseProjection
from praecepta.infra.eventsourcing.projections.rebuilder import ProjectionRebuilder


@pytest.mark.unit
class TestBaseProjectionContract:
    """Tests for BaseProjection abstract contract."""

    def test_cannot_instantiate_without_clear_read_model(self) -> None:
        """BaseProjection requires clear_read_model() implementation."""
        assert hasattr(BaseProjection, "clear_read_model")
        assert getattr(BaseProjection.clear_read_model, "__isabstractmethod__", False)

    def test_has_process_event_method(self) -> None:
        assert hasattr(BaseProjection, "process_event")

    def test_has_upstream_application_attribute(self) -> None:
        assert hasattr(BaseProjection, "upstream_application")

    def test_upstream_application_defaults_to_none(self) -> None:
        assert BaseProjection.upstream_application is None

    def test_default_process_event_tracks_position(self) -> None:
        """Default process_event ignores unknown events but tracks position."""

        class ConcreteProjection(BaseProjection):
            def clear_read_model(self) -> None:
                pass

        mock_view = MagicMock()
        proj = ConcreteProjection(view=mock_view)
        mock_event = MagicMock()
        mock_tracking = MagicMock()

        proj.process_event(mock_event, mock_tracking)

        mock_view.insert_tracking.assert_called_once_with(mock_tracking)

    def test_name_defaults_to_class_name(self) -> None:
        """Projection name should default to class name via __init_subclass__."""

        class MyCustomProjection(BaseProjection):
            def clear_read_model(self) -> None:
                pass

        assert MyCustomProjection.name == "MyCustomProjection"


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
