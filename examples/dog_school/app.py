"""Dog School application factory.

Demonstrates the consumer pattern: bring your domain router,
the framework auto-discovers everything else (middleware, error
handlers, health endpoint) from installed praecepta packages.

Usage::

    from examples.dog_school.app import create_dog_school_app

    app = create_dog_school_app()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from praecepta.infra.fastapi import AppSettings, create_app

if TYPE_CHECKING:
    from fastapi import FastAPI

from .router import router as dog_router

# Entry points excluded because they require external services.
_DEFAULT_EXCLUDE_NAMES = frozenset(
    {
        "api_key_auth",  # Needs API-key repository
        "jwt_auth",  # Needs JWKS endpoint
        "auth",  # Auth lifespan needs JWKS endpoint
        "event_store",  # Needs PostgreSQL
        "persistence",  # Needs PostgreSQL + Redis
        "observability",  # Needs OTel collector (optional, but noisy in dev)
        "taskiq",  # Needs Redis broker
    }
)


def create_dog_school_app(
    *,
    exclude_names: frozenset[str] | None = None,
) -> FastAPI:
    """Create a Dog School app backed by Praecepta.

    Only the domain-specific router is passed explicitly.  Framework
    middleware (request-id, request-context, tenant-state, trace-context),
    error handlers (RFC 7807), and the health endpoint are auto-discovered
    from installed packages — zero manual wiring.

    Args:
        exclude_names: Entry-point names to suppress.  Defaults to auth
            and persistence hooks that need external infrastructure.
    """
    return create_app(
        settings=AppSettings(title="Dog School", version="0.1.0"),
        extra_routers=[dog_router],
        exclude_names=exclude_names if exclude_names is not None else _DEFAULT_EXCLUDE_NAMES,
    )
