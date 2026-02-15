"""Unit tests for praecepta.infra.fastapi.dependencies.feature_flags."""

# NOTE: Do NOT use ``from __future__ import annotations`` here.
# FastAPI Depends() + Annotated requires runtime-evaluable annotations.
# PEP 563 deferred evaluation breaks this under pytest --import-mode=importlib.

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from praecepta.infra.fastapi.dependencies.feature_flags import require_feature
from praecepta.infra.fastapi.middleware.request_context import RequestContextMiddleware


def _make_app(
    *,
    feature_key: str = "feature.graph_view",
    enabled: bool = True,
) -> FastAPI:
    """Create a minimal app with feature flag dependency."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    # Set up feature checker in app state
    def feature_checker(tenant_id: str, key: str) -> bool:
        return enabled

    app.state.feature_checker = feature_checker

    dep = require_feature(feature_key)

    @app.get("/gated")
    def gated_endpoint(_: Annotated[None, Depends(dep)]) -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestRequireFeature:
    @pytest.mark.unit
    def test_enabled_feature_passes(self) -> None:
        app = _make_app(enabled=True)
        client = TestClient(app)
        resp = client.get(
            "/gated",
            headers={
                "X-Tenant-ID": "acme-corp",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    @pytest.mark.unit
    def test_disabled_feature_returns_403(self) -> None:
        app = _make_app(enabled=False)
        # Register error handler for FeatureDisabledError
        from praecepta.infra.fastapi.error_handlers import register_exception_handlers

        register_exception_handlers(app)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/gated",
            headers={
                "X-Tenant-ID": "acme-corp",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body["error_code"] == "FEATURE_DISABLED"

    @pytest.mark.unit
    def test_checker_receives_correct_args(self) -> None:
        """Verify the feature checker receives the tenant_id and feature_key."""
        received: list[tuple[str, str]] = []

        def tracking_checker(tenant_id: str, key: str) -> bool:
            received.append((tenant_id, key))
            return True

        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)
        app.state.feature_checker = tracking_checker

        dep = require_feature("feature.test_flag")

        @app.get("/gated")
        def endpoint(_: Annotated[None, Depends(dep)]) -> dict[str, str]:
            return {"ok": "true"}

        client = TestClient(app)
        client.get(
            "/gated",
            headers={
                "X-Tenant-ID": "test-tenant",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert len(received) == 1
        assert received[0] == ("test-tenant", "feature.test_flag")

    @pytest.mark.unit
    def test_custom_checker_getter(self) -> None:
        """Verify custom checker_getter is used instead of app state."""
        custom_checker_called = False

        def custom_checker(tenant_id: str, key: str) -> bool:
            nonlocal custom_checker_called
            custom_checker_called = True
            return True

        def custom_getter(request: object) -> object:
            return custom_checker

        app = FastAPI()
        app.add_middleware(RequestContextMiddleware)

        dep = require_feature("feature.test", checker_getter=custom_getter)  # type: ignore[arg-type]

        @app.get("/gated")
        def endpoint(_: Annotated[None, Depends(dep)]) -> dict[str, str]:
            return {"ok": "true"}

        client = TestClient(app)
        client.get(
            "/gated",
            headers={
                "X-Tenant-ID": "test-tenant",
                "X-User-ID": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert custom_checker_called is True
