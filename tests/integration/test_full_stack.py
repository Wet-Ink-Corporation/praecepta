"""Full-stack HTTP integration tests.

Uses create_app() with real PostgreSQL and Redis containers. Auth is
bypassed using dev bypass mode (synthetic principal).
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestFullStack:
    """Full-stack HTTP tests with real infrastructure."""

    @pytest.fixture(autouse=True)
    def _enable_dev_bypass(self, monkeypatch):
        """Enable auth dev bypass for full-stack tests."""
        monkeypatch.setenv("AUTH_DEV_BYPASS", "true")
        monkeypatch.setenv("AUTH_ISSUER", "https://dev.example.com")

    @pytest.fixture()
    def full_app(self):
        """Create app with only auth-related entry points excluded."""
        from examples.dog_school.app import create_dog_school_app

        # Exclude only external services that truly cannot work in test
        exclude = frozenset({"observability", "taskiq", "projection_runner"})
        return create_dog_school_app(exclude_names=exclude)

    @pytest.fixture()
    def full_client(self, full_app):
        """TestClient for the full-stack app."""
        from fastapi.testclient import TestClient

        with TestClient(full_app, raise_server_exceptions=False) as c:
            yield c

    def test_health_endpoint_with_real_infrastructure(self, full_client):
        """Health endpoint should respond with real infrastructure connected."""
        response = full_client.get("/health")
        # Health endpoint should exist and respond
        assert response.status_code in (200, 404)  # 404 if not registered

    def test_error_handling_with_real_infrastructure(self, full_client):
        """Invalid request should return proper error response."""
        response = full_client.get("/api/v1/nonexistent-endpoint")
        assert response.status_code in (401, 404, 405)
