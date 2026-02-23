"""Aggregated health check endpoint.

Reports per-subsystem health status for database, Redis, and overall
application readiness.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


async def _check_database() -> dict[str, str]:
    """Check database connectivity via SELECT 1."""
    try:
        from sqlalchemy import text

        from praecepta.infra.persistence.database import get_database_manager

        manager = get_database_manager()
        engine = manager.get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("health_check: database unhealthy: %s", exc)
        return {"status": "error", "detail": str(exc)}


async def _check_redis() -> dict[str, str]:
    """Check Redis connectivity via PING."""
    try:
        from praecepta.infra.persistence.redis_client import get_redis_factory

        factory = get_redis_factory()
        client = await factory.get_client()
        await client.ping()
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("health_check: redis unhealthy: %s", exc)
        return {"status": "error", "detail": str(exc)}


@router.get("/healthz")
async def healthz() -> Any:
    """Aggregated health check endpoint.

    Returns per-subsystem status and an overall status. Returns HTTP 200
    when all subsystems are healthy, HTTP 503 when any subsystem is degraded.
    """
    checks: dict[str, dict[str, str]] = {}

    checks["database"] = await _check_database()
    checks["redis"] = await _check_redis()

    all_ok = all(c["status"] == "ok" for c in checks.values())
    result = {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
    }

    status_code = 200 if all_ok else 503
    return JSONResponse(content=result, status_code=status_code)
