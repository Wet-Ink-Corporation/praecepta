"""Stub health router for discovery self-testing.

This minimal router validates that the entry-point discovery mechanism
works end-to-end. It will be replaced by a full health endpoint in Step 6.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Minimal health check endpoint."""
    return {"status": "ok"}
