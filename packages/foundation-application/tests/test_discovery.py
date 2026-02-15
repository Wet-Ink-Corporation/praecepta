"""Unit tests for praecepta.foundation.application.discovery."""

from __future__ import annotations

import pytest

from praecepta.foundation.application.discovery import DiscoveredContribution, discover


class TestDiscoveredContribution:
    @pytest.mark.unit
    def test_fields(self) -> None:
        contrib = DiscoveredContribution(name="test", group="test.group", value=42)
        assert contrib.name == "test"
        assert contrib.group == "test.group"
        assert contrib.value == 42

    @pytest.mark.unit
    def test_frozen_immutable(self) -> None:
        contrib = DiscoveredContribution(name="test", group="test.group", value=42)
        with pytest.raises(AttributeError):
            contrib.name = "other"  # type: ignore[misc]


class TestDiscover:
    @pytest.mark.unit
    def test_empty_group_returns_empty_list(self) -> None:
        """Discovering from a non-existent group returns an empty list."""
        result = discover("praecepta.nonexistent.group.for.testing")
        assert result == []

    @pytest.mark.unit
    def test_returns_list_of_discovered_contributions(self) -> None:
        result = discover("praecepta.routers")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, DiscoveredContribution)

    @pytest.mark.unit
    def test_exclude_names_filters_entries(self) -> None:
        """Excluded names are skipped without error."""
        result = discover(
            "praecepta.routers",
            exclude_names=frozenset({"nonexistent_name"}),
        )
        assert isinstance(result, list)
