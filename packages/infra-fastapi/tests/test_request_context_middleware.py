"""Unit tests for praecepta.infra.fastapi.middleware.request_context."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from praecepta.foundation.application.context import (
    get_current_context,
    get_current_correlation_id,
    get_current_tenant_id,
    get_current_user_id,
    request_context,
)
from praecepta.infra.fastapi.middleware.request_context import (
    CORRELATION_ID_HEADER,
    TENANT_ID_HEADER,
    USER_ID_HEADER,
    RequestContextMiddleware,
)
from praecepta.infra.fastapi.middleware.request_id import (
    _is_valid_uuid,
)


def _make_app() -> FastAPI:
    """Create a minimal app with RequestContextMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/context")
    def context_endpoint() -> dict[str, str]:
        ctx = get_current_context()
        return {
            "tenant_id": ctx.tenant_id,
            "user_id": str(ctx.user_id),
            "correlation_id": ctx.correlation_id,
        }

    return app


class TestRequestContextMiddleware:
    @pytest.mark.unit
    def test_extracts_all_headers(self) -> None:
        app = _make_app()
        client = TestClient(app)
        user_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        resp = client.get(
            "/context",
            headers={
                TENANT_ID_HEADER: "acme-corp",
                USER_ID_HEADER: user_id,
                CORRELATION_ID_HEADER: correlation_id,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == "acme-corp"
        assert body["user_id"] == user_id
        assert body["correlation_id"] == correlation_id

    @pytest.mark.unit
    def test_generates_correlation_id_when_missing(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get(
            "/context",
            headers={
                TENANT_ID_HEADER: "acme-corp",
                USER_ID_HEADER: str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Correlation ID should be auto-generated as a UUID
        assert _is_valid_uuid(body["correlation_id"])
        # Also in response header
        assert CORRELATION_ID_HEADER in resp.headers

    @pytest.mark.unit
    def test_correlation_id_in_response_header(self) -> None:
        app = _make_app()
        client = TestClient(app)
        correlation_id = str(uuid.uuid4())
        resp = client.get(
            "/context",
            headers={
                TENANT_ID_HEADER: "acme-corp",
                CORRELATION_ID_HEADER: correlation_id,
            },
        )
        assert resp.headers[CORRELATION_ID_HEADER] == correlation_id

    @pytest.mark.unit
    def test_missing_tenant_id_defaults_to_empty(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/context")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == ""

    @pytest.mark.unit
    def test_missing_user_id_defaults_to_nil_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/context")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == str(uuid.UUID(int=0))

    @pytest.mark.unit
    def test_invalid_user_id_defaults_to_nil_uuid(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get(
            "/context",
            headers={USER_ID_HEADER: "not-a-uuid"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == str(uuid.UUID(int=0))

    @pytest.mark.unit
    def test_context_cleared_after_request(self) -> None:
        app = _make_app()
        client = TestClient(app)
        client.get(
            "/context",
            headers={TENANT_ID_HEADER: "acme-corp"},
        )
        # After request completes, context should be cleared
        assert request_context.get() is None


class TestContextAccessorFunctions:
    @pytest.mark.unit
    def test_accessors_within_request(self) -> None:
        """Verify individual accessor functions work within a request."""
        results: dict[str, str] = {}

        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        @app.get("/accessors")
        def accessor_endpoint() -> dict[str, str]:
            results["tenant_id"] = get_current_tenant_id()
            results["user_id"] = str(get_current_user_id())
            results["correlation_id"] = get_current_correlation_id()
            return results

        client = TestClient(app)
        user_id = str(uuid.uuid4())
        resp = client.get(
            "/accessors",
            headers={
                TENANT_ID_HEADER: "test-tenant",
                USER_ID_HEADER: user_id,
                CORRELATION_ID_HEADER: "corr-123",
            },
        )
        assert resp.status_code == 200
        assert results["tenant_id"] == "test-tenant"
        assert results["user_id"] == user_id
        assert results["correlation_id"] == "corr-123"
