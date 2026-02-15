"""Integration tests — middleware stack behaviour through Dog School."""

from __future__ import annotations

from uuid import UUID

import pytest


@pytest.mark.integration
class TestRequestIdPropagation:
    """RequestIdMiddleware generates / propagates X-Request-ID."""

    def test_generates_request_id(self, client) -> None:
        resp = client.get("/healthz")
        rid = resp.headers.get("X-Request-ID", "")
        # Should be a valid UUID
        UUID(rid)

    def test_propagates_provided_request_id(self, client) -> None:
        provided = "12345678-1234-5678-1234-567812345678"
        resp = client.get("/healthz", headers={"X-Request-ID": provided})
        assert resp.headers["X-Request-ID"] == provided


@pytest.mark.integration
class TestCorrelationIdPropagation:
    """RequestContextMiddleware generates / propagates X-Correlation-ID."""

    def test_generates_correlation_id(self, client, tenant_headers) -> None:
        resp = client.get("/healthz", headers=tenant_headers)
        assert "X-Correlation-ID" in resp.headers
        # Should be a valid UUID (auto-generated)
        UUID(resp.headers["X-Correlation-ID"])

    def test_propagates_provided_correlation_id(self, client, tenant_headers) -> None:
        headers = {**tenant_headers, "X-Correlation-ID": "custom-corr-123"}
        resp = client.get("/healthz", headers=headers)
        assert resp.headers["X-Correlation-ID"] == "custom-corr-123"


@pytest.mark.integration
class TestRequestContextInHandlers:
    """Verify headers flow through middleware into request context."""

    def test_tenant_id_available_in_handler(self, client, tenant_headers) -> None:
        """Dog registration uses tenant_id populated by RequestContextMiddleware."""
        resp = client.post("/dogs/", json={"name": "Buddy"}, headers=tenant_headers)
        assert resp.status_code == 201
        assert resp.json()["tenant_id"] == "acme-corp"
