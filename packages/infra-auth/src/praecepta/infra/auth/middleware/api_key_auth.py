"""API key authentication middleware for agent authentication.

Validates X-API-Key header and populates principal context with agent identity.
Runs before JWTAuthMiddleware in the middleware stack to implement first-match-wins:
  - If X-API-Key present -> validate and set principal OR return 401
  - If X-API-Key absent -> delegate to next middleware (JWT)

Design decisions:
  - Separate APIKeyAuthMiddleware (not merged into JWTAuthMiddleware) for SRP
  - Projection-based auth (no aggregate hydration during lookup)
  - RLS bypass for key lookup (auth runs pre-tenant context)

Middleware position in stack (LIFO registration order):
  Request -> RequestId -> TraceContext -> APIKey -> JWT -> RequestContext -> CORS -> Route
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import bcrypt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from praecepta.foundation.application.context import (
    clear_principal_context,
    get_optional_principal,
    set_principal_context,
)
from praecepta.foundation.application.contributions import MiddlewareContribution
from praecepta.foundation.domain.principal import Principal, PrincipalType

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response


logger = logging.getLogger(__name__)

# Default paths excluded from API key authentication.
_DEFAULT_EXCLUDED_PREFIXES = (
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
)

_PROBLEM_MEDIA_TYPE = "application/problem+json"


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API key validation middleware for agent authentication.

    Request flow:
    1. Check if path is excluded -> skip auth
    2. Check if X-API-Key header present -> validate API key
       a. Extract key_id from key format: {prefix}{key_id}{secret}
       b. Look up key metadata from agent_api_key_registry projection
       c. Verify bcrypt hash (timing-safe comparison)
       d. Check key status (active vs revoked)
       e. Set principal context with agent_id, tenant_id, PrincipalType.AGENT
    3. If X-API-Key absent -> delegate to next middleware (JWT)

    Error flow:
    - Missing header -> pass to next middleware (JWT)
    - Malformed key -> 401 (invalid_format)
    - Unknown key_id -> 401 (invalid_key)
    - Revoked key -> 401 (revoked_key)
    - Hash mismatch -> 401 (invalid_key)

    All 401 responses include WWW-Authenticate: APIKey header.
    """

    def __init__(
        self,
        app: Any,
        key_prefix: str = "pk_",
        excluded_prefixes: tuple[str, ...] | None = None,
    ) -> None:
        """Initialize API key authentication middleware.

        Args:
            app: ASGI application (passed by Starlette).
            key_prefix: Expected API key prefix (default: ``pk_``).
            excluded_prefixes: Path prefixes to skip auth on.
                Defaults to /health, /ready, /docs, /openapi.json, /redoc.

        Note:
            Repository is retrieved lazily from request.app.state.agent_api_key_repo
            during request processing. This allows middleware registration before
            lifespan initialization.
        """
        super().__init__(app)
        self._key_prefix = key_prefix
        self._prefix_len = len(key_prefix)
        self._excluded_prefixes = (
            excluded_prefixes if excluded_prefixes is not None else _DEFAULT_EXCLUDED_PREFIXES
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with API key validation.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in stack.

        Returns:
            Response from handler or auth error response.
        """
        # 1. Skip excluded paths
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._excluded_prefixes):
            return await call_next(request)

        # 2. Check if principal already set by earlier middleware
        if get_optional_principal() is not None:
            return await call_next(request)

        # 3. Extract X-API-Key header
        api_key_header = request.headers.get("X-API-Key", "")
        if not api_key_header:
            # No API key -> delegate to JWTAuthMiddleware for JWT validation
            return await call_next(request)

        # 4. Parse key format: {prefix}{key_id}{secret}
        if not api_key_header.startswith(self._key_prefix):
            return self._auth_error(
                request,
                401,
                "invalid_format",
                f"API key must start with '{self._key_prefix}' prefix",
            )

        # prefix (N) + key_id (8) + secret (min 1)
        min_length = self._prefix_len + 8 + 1
        if len(api_key_header) < min_length:
            return self._auth_error(
                request,
                401,
                "invalid_format",
                "API key format is invalid",
            )

        key_id = api_key_header[self._prefix_len : self._prefix_len + 8]
        secret = api_key_header[self._prefix_len + 8 :]

        # 5. Get repository from app state (initialized during lifespan)
        repo = request.app.state.agent_api_key_repo

        # 6. Look up key metadata from projection (runs WITHOUT RLS)
        key_record = repo.lookup_by_key_id(key_id)
        if key_record is None:
            logger.info(
                "api_key_auth_unknown_key",
                extra={
                    "key_id": key_id,
                    "path": path,
                    "method": request.method,
                },
            )
            return self._auth_error(
                request,
                401,
                "invalid_key",
                "API key is invalid or does not exist",
            )

        # 7. Check key status (revoked keys rejected before bcrypt)
        if key_record.status != "active":
            logger.info(
                "api_key_auth_revoked",
                extra={
                    "key_id": key_id,
                    "agent_id": str(key_record.agent_id),
                    "status": key_record.status,
                    "path": path,
                },
            )
            return self._auth_error(
                request,
                401,
                "revoked_key",
                "API key has been revoked",
            )

        # 8. Verify bcrypt hash (timing-safe comparison)
        try:
            is_valid = bcrypt.checkpw(
                secret.encode("utf-8"),
                key_record.key_hash.encode("utf-8"),
            )
        except Exception:
            logger.exception(
                "api_key_auth_bcrypt_error",
                extra={
                    "key_id": key_id,
                    "agent_id": str(key_record.agent_id),
                },
            )
            return self._auth_error(
                request,
                401,
                "invalid_key",
                "API key validation failed",
            )

        if not is_valid:
            logger.info(
                "api_key_auth_hash_mismatch",
                extra={
                    "key_id": key_id,
                    "agent_id": str(key_record.agent_id),
                    "path": path,
                },
            )
            return self._auth_error(
                request,
                401,
                "invalid_key",
                "API key is invalid",
            )

        # 9. Extract principal from key metadata
        principal = Principal(
            subject=str(key_record.agent_id),
            tenant_id=key_record.tenant_id,
            user_id=key_record.agent_id,
            roles=("agent",),
            email=None,
            principal_type=PrincipalType.AGENT,
        )

        # 10. Log successful authentication (NEVER log full key, only key_id)
        logger.info(
            "api_key_auth_success",
            extra={
                "key_id": key_id,
                "agent_id": str(key_record.agent_id),
                "tenant_id": key_record.tenant_id,
                "path": path,
            },
        )

        # 11. Set principal context and continue to next handler
        principal_token = set_principal_context(principal)
        try:
            return await call_next(request)
        finally:
            clear_principal_context(principal_token)

    def _auth_error(
        self,
        request: Request,
        status_code: int,
        error_code: str,
        message: str,
    ) -> JSONResponse:
        """Build RFC 7807 compliant error response with WWW-Authenticate header.

        Args:
            request: Current request (for instance path and logging).
            status_code: HTTP status code (401).
            error_code: Machine-readable error code (snake_case).
            message: Human-readable error description.

        Returns:
            JSONResponse with problem details and WWW-Authenticate header.
        """
        headers: dict[str, str] = {}
        if status_code == 401:
            headers["WWW-Authenticate"] = (
                f'APIKey realm="API", error="{error_code}", error_description="{message}"'
            )

        return JSONResponse(
            status_code=status_code,
            content={
                "type": f"/errors/{error_code.replace('_', '-')}",
                "title": "Unauthorized",
                "status": status_code,
                "detail": message,
                "error_code": error_code.upper(),
                "instance": str(request.url.path),
            },
            media_type=_PROBLEM_MEDIA_TYPE,
            headers=headers,
        )


contribution = MiddlewareContribution(
    middleware_class=APIKeyAuthMiddleware,
    priority=100,  # Security band (100-199)
)
