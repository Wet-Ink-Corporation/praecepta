"""Unit tests for praecepta.infra.fastapi.app_factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from praecepta.foundation.application.contributions import (
    ErrorHandlerContribution,
    LifespanContribution,
)
from praecepta.infra.fastapi import AppSettings, create_app

# Exclude all discovery groups so tests are isolated from installed entry points
_ALL_GROUPS = frozenset(
    {
        "praecepta.routers",
        "praecepta.middleware",
        "praecepta.error_handlers",
        "praecepta.lifespan",
    }
)


class TestCreateAppBasic:
    """Tests for create_app() with discovery suppressed."""

    @pytest.mark.unit
    def test_returns_fastapi_instance(self) -> None:
        app = create_app(settings=AppSettings(), exclude_groups=_ALL_GROUPS)
        assert isinstance(app, FastAPI)

    @pytest.mark.unit
    def test_applies_settings(self) -> None:
        app = create_app(
            settings=AppSettings(title="My Title", version="1.2.3"),
            exclude_groups=_ALL_GROUPS,
        )
        assert app.title == "My Title"
        assert app.version == "1.2.3"

    @pytest.mark.unit
    def test_default_settings(self) -> None:
        app = create_app(exclude_groups=_ALL_GROUPS)
        assert app.title == "Praecepta Application"


class TestCreateAppExtraRouters:
    @pytest.mark.unit
    def test_extra_router_is_mounted(self) -> None:
        router = APIRouter(prefix="/test")

        @router.get("/ping")
        def ping() -> dict[str, str]:
            return {"status": "ok"}

        app = create_app(
            settings=AppSettings(),
            extra_routers=[router],
            exclude_groups=_ALL_GROUPS,
        )
        client = TestClient(app)
        response = client.get("/test/ping")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCreateAppExtraErrorHandlers:
    @pytest.mark.unit
    def test_extra_error_handler_is_registered(self) -> None:
        class CustomError(Exception):
            pass

        async def custom_handler(request: object, exc: CustomError) -> object:  # type: ignore[override]
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=418, content={"error": "teapot"})

        app = create_app(
            settings=AppSettings(),
            extra_error_handlers=[
                ErrorHandlerContribution(
                    exception_class=CustomError,
                    handler=custom_handler,
                ),
            ],
            exclude_groups=_ALL_GROUPS,
        )

        @app.get("/fail")
        def fail() -> None:
            raise CustomError("boom")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/fail")
        assert response.status_code == 418
        assert response.json() == {"error": "teapot"}


class TestCreateAppExtraLifespan:
    @pytest.mark.unit
    def test_extra_lifespan_hook_executes(self) -> None:
        started: list[bool] = []

        @asynccontextmanager
        async def hook(app: FastAPI) -> AsyncIterator[None]:
            started.append(True)
            yield

        app = create_app(
            settings=AppSettings(),
            extra_lifespan_hooks=[LifespanContribution(hook=hook, priority=100)],
            exclude_groups=_ALL_GROUPS,
        )
        with TestClient(app):
            assert started == [True]

    @pytest.mark.unit
    def test_multiple_lifespan_hooks_in_order(self) -> None:
        order: list[str] = []

        @asynccontextmanager
        async def hook_first(app: FastAPI) -> AsyncIterator[None]:
            order.append("first")
            yield

        @asynccontextmanager
        async def hook_second(app: FastAPI) -> AsyncIterator[None]:
            order.append("second")
            yield

        app = create_app(
            settings=AppSettings(),
            extra_lifespan_hooks=[
                LifespanContribution(hook=hook_second, priority=200),
                LifespanContribution(hook=hook_first, priority=100),
            ],
            exclude_groups=_ALL_GROUPS,
        )
        with TestClient(app):
            assert order == ["first", "second"]
