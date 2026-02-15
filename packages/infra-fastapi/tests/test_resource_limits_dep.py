"""Unit tests for praecepta.infra.fastapi.dependencies.resource_limits."""

# NOTE: Do NOT use ``from __future__ import annotations`` here.
# FastAPI Depends() + Annotated requires runtime-evaluable annotations.
# PEP 563 deferred evaluation breaks this under pytest --import-mode=importlib.

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from praecepta.infra.fastapi.dependencies.resource_limits import (
    ResourceLimitResult,
    check_resource_limit,
)
from praecepta.infra.fastapi.middleware.request_context import RequestContextMiddleware


def _make_app(
    *,
    usage_counter: object | None = None,
    limit_resolver: object | None = None,
    default_limit: int = 2**31 - 1,
) -> FastAPI:
    """Create a minimal app with resource limit dependency."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    kwargs: dict[str, object] = {}
    if usage_counter is not None:
        kwargs["usage_counter"] = usage_counter
    if limit_resolver is not None:
        kwargs["limit_resolver"] = limit_resolver
    kwargs["default_limit"] = default_limit

    dep = check_resource_limit("test_resource", **kwargs)  # type: ignore[arg-type]

    @app.post("/create")
    def create_endpoint(
        result: Annotated[ResourceLimitResult, Depends(dep)],
    ) -> dict[str, int]:
        return {"limit": result.limit, "remaining": result.remaining}

    return app


class TestCheckResourceLimit:
    @pytest.mark.unit
    def test_within_limit_returns_result(self) -> None:
        app = _make_app(
            usage_counter=lambda req, tid, res: 5,
            limit_resolver=lambda req, tid, res: 100,
        )
        client = TestClient(app)
        resp = client.post(
            "/create",
            headers={
                "X-Tenant-ID": "acme-corp",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 100
        # remaining = 100 - 5 - 1 = 94
        assert body["remaining"] == 94

    @pytest.mark.unit
    def test_at_limit_returns_429(self) -> None:
        from praecepta.infra.fastapi.error_handlers import register_exception_handlers

        app = _make_app(
            usage_counter=lambda req, tid, res: 100,
            limit_resolver=lambda req, tid, res: 100,
        )
        register_exception_handlers(app)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/create",
            headers={
                "X-Tenant-ID": "acme-corp",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 429
        body = resp.json()
        assert body["error_code"] == "RESOURCE_LIMIT_EXCEEDED"

    @pytest.mark.unit
    def test_no_counter_defaults_to_zero_usage(self) -> None:
        """Without usage_counter, usage is 0 so limit is never exceeded."""
        app = _make_app(
            limit_resolver=lambda req, tid, res: 10,
        )
        client = TestClient(app)
        resp = client.post(
            "/create",
            headers={
                "X-Tenant-ID": "acme-corp",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 10
        # remaining = 10 - 0 - 1 = 9
        assert body["remaining"] == 9

    @pytest.mark.unit
    def test_no_resolver_uses_default_limit(self) -> None:
        app = _make_app(
            usage_counter=lambda req, tid, res: 0,
            default_limit=50,
        )
        client = TestClient(app)
        resp = client.post(
            "/create",
            headers={
                "X-Tenant-ID": "acme-corp",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 50

    @pytest.mark.unit
    def test_resource_limit_result_dataclass(self) -> None:
        result = ResourceLimitResult(limit=100, remaining=42)
        assert result.limit == 100
        assert result.remaining == 42

    @pytest.mark.unit
    def test_counter_receives_correct_args(self) -> None:
        """Verify usage_counter receives (request, tenant_id, resource)."""
        received: list[tuple[str, str]] = []

        def tracking_counter(request: object, tenant_id: str, resource: str) -> int:
            received.append((tenant_id, resource))
            return 0

        app = _make_app(usage_counter=tracking_counter, default_limit=100)
        client = TestClient(app)
        client.post(
            "/create",
            headers={
                "X-Tenant-ID": "track-tenant",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert len(received) == 1
        assert received[0] == ("track-tenant", "test_resource")

    @pytest.mark.unit
    def test_limit_exactly_one_over(self) -> None:
        """When current + 1 > limit, should raise ResourceLimitExceededError."""
        from praecepta.infra.fastapi.error_handlers import register_exception_handlers

        app = _make_app(
            usage_counter=lambda req, tid, res: 10,
            limit_resolver=lambda req, tid, res: 10,
        )
        register_exception_handlers(app)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/create",
            headers={
                "X-Tenant-ID": "acme-corp",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 429
