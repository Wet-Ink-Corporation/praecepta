"""Integration tests: entry-point discovery finds the stub health router."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from praecepta.foundation.application.discovery import discover
from praecepta.infra.fastapi import AppSettings, create_app


class TestDiscoveryIntegration:
    @pytest.mark.unit
    def test_discover_finds_health_stub_router(self) -> None:
        """The _health_stub entry point is discovered from infra-fastapi."""
        results = discover("praecepta.routers")
        names = [r.name for r in results]
        assert "_health_stub" in names

    @pytest.mark.unit
    def test_create_app_auto_discovers_health_endpoint(self) -> None:
        """create_app() without router exclusion discovers and mounts /healthz."""
        app = create_app(settings=AppSettings(title="Discovery Test"))
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.unit
    def test_exclude_routers_group_hides_health(self) -> None:
        """Excluding the routers group prevents /healthz from appearing."""
        app = create_app(
            settings=AppSettings(),
            exclude_groups=frozenset({"praecepta.routers"}),
        )
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 404

    @pytest.mark.unit
    def test_exclude_name_hides_specific_entry_point(self) -> None:
        """Excluding a specific name skips just that contribution."""
        app = create_app(
            settings=AppSettings(),
            exclude_names=frozenset({"_health_stub"}),
        )
        client = TestClient(app)
        response = client.get("/healthz")
        assert response.status_code == 404
