"""Unit tests for praecepta.infra.fastapi.middleware.tenant_state."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from praecepta.foundation.domain import TenantStatus
from praecepta.infra.fastapi.middleware.tenant_state import (
    DEFAULT_EXCLUDED_PREFIXES,
    TenantStateMiddleware,
)


def _make_app(
    *,
    checker: object | None = None,
    excluded_prefixes: tuple[str, ...] | None = None,
) -> FastAPI:
    """Create a minimal app with TenantStateMiddleware."""
    app = FastAPI()

    kwargs: dict[str, object] = {}
    if checker is not None:
        kwargs["tenant_status_checker"] = checker
    if excluded_prefixes is not None:
        kwargs["excluded_prefixes"] = excluded_prefixes

    app.add_middleware(TenantStateMiddleware, **kwargs)

    @app.get("/api/data")
    def data_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health")
    def health_endpoint() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/custom-excluded")
    def custom_excluded_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestTenantStateMiddleware:
    @pytest.mark.unit
    def test_excluded_paths_bypass_check(self) -> None:
        """Default excluded paths like /health should bypass enforcement."""
        # Use a checker that always returns SUSPENDED to verify bypass
        app = _make_app(checker=lambda slug: TenantStatus.SUSPENDED.value)
        client = TestClient(app)
        resp = client.get(
            "/health",
            headers={"X-Tenant-ID": "acme-corp"},
        )
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_suspended_tenant_returns_403(self) -> None:
        app = _make_app(checker=lambda slug: TenantStatus.SUSPENDED.value)
        client = TestClient(app)
        resp = client.get(
            "/api/data",
            headers={"X-Tenant-ID": "acme-corp"},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body["type"] == "/errors/tenant-suspended"
        assert body["error_code"] == "TENANT_SUSPENDED"
        assert "acme-corp" in body["detail"]
        assert "suspended" in body["detail"]

    @pytest.mark.unit
    def test_decommissioned_tenant_returns_403(self) -> None:
        app = _make_app(checker=lambda slug: TenantStatus.DECOMMISSIONED.value)
        client = TestClient(app)
        resp = client.get(
            "/api/data",
            headers={"X-Tenant-ID": "old-corp"},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body["error_code"] == "TENANT_SUSPENDED"
        assert "decommissioned" in body["detail"]

    @pytest.mark.unit
    def test_active_tenant_passes_through(self) -> None:
        app = _make_app(checker=lambda slug: TenantStatus.ACTIVE.value)
        client = TestClient(app)
        resp = client.get(
            "/api/data",
            headers={"X-Tenant-ID": "acme-corp"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @pytest.mark.unit
    def test_fail_open_on_cache_miss(self) -> None:
        """When checker returns None (cache miss), requests should be allowed."""
        app = _make_app(checker=lambda slug: None)
        client = TestClient(app)
        resp = client.get(
            "/api/data",
            headers={"X-Tenant-ID": "new-tenant"},
        )
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_fail_open_when_no_checker(self) -> None:
        """When no checker is provided, all requests pass through."""
        app = _make_app()
        client = TestClient(app)
        resp = client.get(
            "/api/data",
            headers={"X-Tenant-ID": "acme-corp"},
        )
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_no_tenant_header_passes_through(self) -> None:
        """Requests without X-Tenant-ID should pass through."""
        app = _make_app(checker=lambda slug: TenantStatus.SUSPENDED.value)
        client = TestClient(app)
        resp = client.get("/api/data")
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_configurable_excluded_prefixes(self) -> None:
        """Custom excluded prefixes override defaults."""
        app = _make_app(
            checker=lambda slug: TenantStatus.SUSPENDED.value,
            excluded_prefixes=("/custom-excluded", "/health"),
        )
        client = TestClient(app)
        # Custom-excluded path should bypass
        resp = client.get(
            "/custom-excluded",
            headers={"X-Tenant-ID": "acme-corp"},
        )
        assert resp.status_code == 200

        # Non-excluded path should be blocked
        resp = client.get(
            "/api/data",
            headers={"X-Tenant-ID": "acme-corp"},
        )
        assert resp.status_code == 403

    @pytest.mark.unit
    def test_problem_media_type_in_response(self) -> None:
        """403 responses should have application/problem+json content type."""
        app = _make_app(checker=lambda slug: TenantStatus.SUSPENDED.value)
        client = TestClient(app)
        resp = client.get(
            "/api/data",
            headers={"X-Tenant-ID": "acme-corp"},
        )
        assert "application/problem+json" in resp.headers["content-type"]

    @pytest.mark.unit
    def test_default_excluded_prefixes_contain_common_paths(self) -> None:
        """Verify default excluded prefixes include standard infra paths."""
        assert "/health" in DEFAULT_EXCLUDED_PREFIXES
        assert "/ready" in DEFAULT_EXCLUDED_PREFIXES
        assert "/docs" in DEFAULT_EXCLUDED_PREFIXES
        assert "/openapi.json" in DEFAULT_EXCLUDED_PREFIXES

    @pytest.mark.unit
    def test_checker_receives_tenant_slug(self) -> None:
        """Verify the checker callable receives the correct tenant slug."""
        received_slugs: list[str] = []

        def tracking_checker(slug: str) -> str | None:
            received_slugs.append(slug)
            return TenantStatus.ACTIVE.value

        app = _make_app(checker=tracking_checker)
        client = TestClient(app)
        client.get(
            "/api/data",
            headers={"X-Tenant-ID": "test-tenant-xyz"},
        )
        assert received_slugs == ["test-tenant-xyz"]
