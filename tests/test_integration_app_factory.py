"""Integration tests — create_app() auto-discovery with Dog School."""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestAutoDiscovery:
    """Prove create_app() discovers and wires contributions from installed packages."""

    def test_health_endpoint_discovered(self, client) -> None:
        """Auto-discovered _health_stub router serves /healthz."""
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_dog_router_mounted(self, client, tenant_headers) -> None:
        """extra_routers works alongside auto-discovered routers."""
        resp = client.post("/dogs/", json={"name": "Fido"}, headers=tenant_headers)
        assert resp.status_code == 201

    def test_error_handlers_produce_problem_json(self, client, tenant_headers) -> None:
        """Auto-discovered rfc7807 error handlers set correct content type."""
        resp = client.get(
            "/dogs/00000000-0000-0000-0000-000000000099",
            headers=tenant_headers,
        )
        assert resp.status_code == 404
        assert "application/problem+json" in resp.headers["content-type"]

    def test_cors_headers_on_preflight(self, client) -> None:
        """CORS middleware is applied (default: allow all origins)."""
        resp = client.options(
            "/healthz",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" in resp.headers
