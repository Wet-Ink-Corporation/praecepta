"""FastAPI application factory with entry-point auto-discovery.

Provides :func:`create_app` which discovers and wires routers, middleware,
error handlers, and lifespan hooks from installed praecepta packages.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.middleware.cors import CORSMiddleware

from fastapi import FastAPI
from praecepta.foundation.application import (
    ErrorHandlerContribution,
    LifespanContribution,
    MiddlewareContribution,
    discover,
)
from praecepta.infra.fastapi.lifespan import compose_lifespan
from praecepta.infra.fastapi.settings import AppSettings

if TYPE_CHECKING:
    from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Entry point group constants
GROUP_ROUTERS = "praecepta.routers"
GROUP_MIDDLEWARE = "praecepta.middleware"
GROUP_ERROR_HANDLERS = "praecepta.error_handlers"
GROUP_LIFESPAN = "praecepta.lifespan"


def create_app(
    settings: AppSettings | None = None,
    *,
    extra_routers: list[APIRouter] | None = None,
    extra_middleware: list[MiddlewareContribution] | None = None,
    extra_lifespan_hooks: list[LifespanContribution] | None = None,
    extra_error_handlers: list[ErrorHandlerContribution] | None = None,
    exclude_groups: frozenset[str] | None = None,
    exclude_names: frozenset[str] | None = None,
) -> FastAPI:
    """Create a FastAPI application with auto-discovered contributions.

    Discovers routers, middleware, error handlers, and lifespan hooks from
    installed packages via Python entry points, then wires them into a
    FastAPI application.

    Args:
        settings: Application settings. If ``None``, loaded from environment.
        extra_routers: Additional routers to include beyond discovered ones.
        extra_middleware: Additional middleware beyond discovered ones.
        extra_lifespan_hooks: Additional lifespan hooks beyond discovered ones.
        extra_error_handlers: Additional error handlers beyond discovered ones.
        exclude_groups: Entry point groups to skip entirely.
        exclude_names: Specific entry point names to skip across all groups.

    Returns:
        Configured FastAPI application instance.
    """
    settings = settings or AppSettings()
    _exclude_groups = exclude_groups if exclude_groups is not None else settings.exclude_groups
    _exclude_names = exclude_names if exclude_names is not None else settings.exclude_entry_points

    # --- Discover lifespan hooks ---
    lifespan_hooks: list[LifespanContribution] = list(extra_lifespan_hooks or [])
    if GROUP_LIFESPAN not in _exclude_groups:
        for contrib in discover(GROUP_LIFESPAN, exclude_names=_exclude_names):
            value = contrib.value
            if isinstance(value, LifespanContribution):
                lifespan_hooks.append(value)
            else:
                # Assume bare async context manager factory; wrap with default priority
                lifespan_hooks.append(LifespanContribution(hook=value))

    composed_lifespan = compose_lifespan(lifespan_hooks)

    # --- Create FastAPI app ---
    app = FastAPI(
        title=settings.title,
        version=settings.version,
        description=settings.description,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        debug=settings.debug,
        lifespan=composed_lifespan,
    )

    # --- CORS (always added, configured via settings) ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allow_origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
        expose_headers=settings.cors.expose_headers,
    )

    # --- Discover and register middleware ---
    middleware_contribs: list[MiddlewareContribution] = list(extra_middleware or [])
    if GROUP_MIDDLEWARE not in _exclude_groups:
        for contrib in discover(GROUP_MIDDLEWARE, exclude_names=_exclude_names):
            value = contrib.value
            if isinstance(value, MiddlewareContribution):
                middleware_contribs.append(value)
            else:
                logger.warning(
                    "Middleware entry point %r did not return a MiddlewareContribution",
                    contrib.name,
                )

    # Sort by priority ascending, then add in reverse (LIFO for Starlette)
    middleware_contribs.sort(key=lambda m: m.priority)
    for mw in reversed(middleware_contribs):
        app.add_middleware(mw.middleware_class, **mw.kwargs)
        logger.info(
            "Registered middleware %s (priority=%d)",
            mw.middleware_class.__name__,
            mw.priority,
        )

    # --- Discover and register error handlers ---
    error_handler_contribs: list[ErrorHandlerContribution] = list(extra_error_handlers or [])
    if GROUP_ERROR_HANDLERS not in _exclude_groups:
        for contrib in discover(GROUP_ERROR_HANDLERS, exclude_names=_exclude_names):
            value = contrib.value
            if isinstance(value, ErrorHandlerContribution):
                error_handler_contribs.append(value)
            elif callable(value):
                # Allow a register function: register(app) -> None
                value(app)
            else:
                logger.warning(
                    "Error handler entry point %r is not an ErrorHandlerContribution or callable",
                    contrib.name,
                )

    for eh in error_handler_contribs:
        app.add_exception_handler(eh.exception_class, eh.handler)
        logger.info("Registered error handler for %s", eh.exception_class.__name__)

    # --- Discover and include routers ---
    routers: list[APIRouter] = list(extra_routers or [])
    if GROUP_ROUTERS not in _exclude_groups:
        for contrib in discover(GROUP_ROUTERS, exclude_names=_exclude_names):
            routers.append(contrib.value)

    for router in routers:
        app.include_router(router)
        logger.info("Included router: %r", router)

    return app
