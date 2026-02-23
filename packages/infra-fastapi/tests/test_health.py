"""Tests for aggregated health check endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from praecepta.infra.fastapi._health import router


@pytest.fixture
def health_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.unit
class TestHealthz:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_all_healthy(self, health_app: FastAPI) -> None:
        with (
            patch(
                "praecepta.infra.fastapi._health._check_database",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
            patch(
                "praecepta.infra.fastapi._health._check_redis",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
        ):
            transport = ASGITransport(app=health_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/healthz")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ok"
            assert body["checks"]["database"]["status"] == "ok"
            assert body["checks"]["redis"]["status"] == "ok"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_degraded_when_db_fails(self, health_app: FastAPI) -> None:
        with (
            patch(
                "praecepta.infra.fastapi._health._check_database",
                new_callable=AsyncMock,
                return_value={"status": "error", "detail": "conn refused"},
            ),
            patch(
                "praecepta.infra.fastapi._health._check_redis",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
        ):
            transport = ASGITransport(app=health_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/healthz")
            assert resp.status_code == 503
            body = resp.json()
            assert body["status"] == "degraded"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_degraded_when_redis_fails(self, health_app: FastAPI) -> None:
        with (
            patch(
                "praecepta.infra.fastapi._health._check_database",
                new_callable=AsyncMock,
                return_value={"status": "ok"},
            ),
            patch(
                "praecepta.infra.fastapi._health._check_redis",
                new_callable=AsyncMock,
                return_value={"status": "error", "detail": "timeout"},
            ),
        ):
            transport = ASGITransport(app=health_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/healthz")
            assert resp.status_code == 503
            body = resp.json()
            assert body["status"] == "degraded"
