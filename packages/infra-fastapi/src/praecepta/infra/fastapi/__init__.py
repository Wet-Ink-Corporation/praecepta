"""Praecepta Infra FastAPI — error handlers, middleware, dependencies, app factory."""

from praecepta.foundation.application.context import (
    NoRequestContextError,
    RequestContext,
    clear_request_context,
    get_current_context,
    get_current_correlation_id,
    get_current_tenant_id,
    get_current_user_id,
    set_request_context,
)
from praecepta.infra.fastapi.app_factory import create_app
from praecepta.infra.fastapi.error_handlers import (
    ProblemDetail,
    register_exception_handlers,
)
from praecepta.infra.fastapi.middleware.request_context import RequestContextMiddleware
from praecepta.infra.fastapi.middleware.request_id import (
    RequestIdMiddleware,
    get_request_id,
)
from praecepta.infra.fastapi.middleware.tenant_state import TenantStateMiddleware
from praecepta.infra.fastapi.settings import AppSettings, CORSSettings

__all__ = [
    "AppSettings",
    "CORSSettings",
    "NoRequestContextError",
    "ProblemDetail",
    "RequestContext",
    "RequestContextMiddleware",
    "RequestIdMiddleware",
    "TenantStateMiddleware",
    "clear_request_context",
    "create_app",
    "get_current_context",
    "get_current_correlation_id",
    "get_current_tenant_id",
    "get_current_user_id",
    "get_request_id",
    "register_exception_handlers",
    "set_request_context",
]
