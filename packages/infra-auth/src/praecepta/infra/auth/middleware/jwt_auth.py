"""JWT authentication middleware for RS256 token validation.

Validates Bearer tokens on all requests except excluded paths.
Stores decoded claims in request.state.jwt_claims for downstream
extraction by principal context.

Middleware position in stack (LIFO registration order):
  Request -> RequestId -> TraceContext -> Auth -> RequestContext -> CORS -> Route

Design decisions:
- Use BaseHTTPMiddleware (not pure ASGI) for consistency with other
  middleware. Performance overhead is negligible (<0.1ms) vs JWT
  validation time (~1-3ms).
- Return JSONResponse directly for auth errors (not raise HTTPException)
  because BaseHTTPMiddleware dispatch cannot propagate exceptions through
  the ASGI stack.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from praecepta.foundation.application.context import (
    clear_principal_context,
    get_optional_principal,
    set_principal_context,
)
from praecepta.foundation.application.contributions import MiddlewareContribution
from praecepta.foundation.domain.principal import Principal, PrincipalType
from praecepta.infra.auth.dev_bypass import resolve_dev_bypass

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

    from praecepta.infra.auth.jwks import JWKSProvider

logger = logging.getLogger(__name__)

# Default paths excluded from JWT validation.
_DEFAULT_EXCLUDED_PREFIXES = (
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
)

_PROBLEM_MEDIA_TYPE = "application/problem+json"


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """JWT validation middleware with RS256 signature verification.

    Request flow:
    1. Check if path is excluded -> skip auth
    2. Check dev bypass -> inject synthetic claims if active
    3. Extract Authorization: Bearer <token> header
    4. Validate JWT signature via JWKSProvider (RS256 only)
    5. Validate standard claims: exp, iss, aud
    6. Store decoded claims in request.state.jwt_claims
    7. Call next middleware/handler

    Error flow:
    - Missing header -> 401 (missing_token)
    - Malformed header -> 401 (invalid_format)
    - Expired token -> 401 (token_expired)
    - Invalid signature -> 401 (invalid_signature)
    - Invalid claims -> 401 (invalid_claims)
    - Malformed JWT -> 401 (invalid_token)

    All 401 responses include WWW-Authenticate: Bearer header per RFC 6750.
    """

    def __init__(
        self,
        app: Any,
        jwks_provider: JWKSProvider | None = None,
        issuer: str = "",
        audience: str = "api",
        dev_bypass: bool = False,
        excluded_prefixes: tuple[str, ...] | None = None,
    ) -> None:
        """Initialize authentication middleware.

        Args:
            app: ASGI application (passed by Starlette).
            jwks_provider: JWKS key provider for signature verification.
                None if dev bypass is active or issuer not configured.
            issuer: Expected JWT issuer claim value.
            audience: Expected JWT audience claim value.
            dev_bypass: Whether dev bypass was requested. Subject to
                production safety check via resolve_dev_bypass().
            excluded_prefixes: Path prefixes to skip auth on.
                Defaults to /health, /ready, /docs, /openapi.json, /redoc.
        """
        super().__init__(app)
        self._jwks_provider = jwks_provider
        self._issuer = issuer
        self._audience = audience
        self._dev_bypass = resolve_dev_bypass(dev_bypass)
        self._excluded_prefixes = (
            excluded_prefixes if excluded_prefixes is not None else _DEFAULT_EXCLUDED_PREFIXES
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with JWT validation.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in stack.

        Returns:
            Response from handler or auth error response.
        """
        # 0. Check if principal already set by APIKeyMiddleware (first-match-wins)
        if get_optional_principal() is not None:
            return await call_next(request)

        # 1. Skip excluded paths
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self._excluded_prefixes):
            return await call_next(request)

        # 2. Check dev bypass (only when no Authorization header)
        auth_header = request.headers.get("Authorization", "")
        if self._dev_bypass and not auth_header:
            from praecepta.infra.auth import DEV_BYPASS_CLAIMS

            claims = dict(DEV_BYPASS_CLAIMS)
            request.state.jwt_claims = claims

            # Extract principal from dev bypass claims
            try:
                principal = _extract_principal(claims)
            except ValueError as exc:
                return self._auth_error(request, 401, "invalid_claims", str(exc))

            principal_token = set_principal_context(principal)
            try:
                return await call_next(request)
            finally:
                clear_principal_context(principal_token)

        # 3. Extract Bearer token
        if not auth_header:
            return self._auth_error(
                request,
                401,
                "missing_token",
                "Authorization header is required",
            )

        if not auth_header.startswith("Bearer "):
            return self._auth_error(
                request,
                401,
                "invalid_format",
                "Authorization header must use Bearer scheme",
            )

        token = auth_header[7:]  # len("Bearer ") == 7
        if not token:
            return self._auth_error(request, 401, "invalid_format", "Bearer token is empty")

        # 4-5. Validate JWT
        if self._jwks_provider is None:
            return self._auth_error(
                request,
                503,
                "service_unavailable",
                "Authentication service not configured",
            )

        try:
            signing_key = self._jwks_provider.get_signing_key_from_jwt(token)
            claims = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except pyjwt.ExpiredSignatureError:
            return self._auth_error(request, 401, "token_expired", "Token has expired")
        except pyjwt.InvalidIssuerError:
            return self._auth_error(request, 401, "invalid_claims", "Invalid issuer claim")
        except pyjwt.InvalidAudienceError:
            return self._auth_error(request, 401, "invalid_claims", "Invalid audience claim")
        except pyjwt.MissingRequiredClaimError as exc:
            return self._auth_error(
                request,
                401,
                "invalid_claims",
                f"Missing required claim: {exc}",
            )
        except pyjwt.InvalidSignatureError:
            return self._auth_error(
                request,
                401,
                "invalid_signature",
                "Token signature verification failed",
            )
        except pyjwt.DecodeError:
            return self._auth_error(request, 401, "invalid_token", "Token is malformed")
        except pyjwt.InvalidTokenError:
            return self._auth_error(request, 401, "invalid_token", "Token validation failed")
        except Exception:
            logger.exception("jwt_validation_unexpected_error")
            return self._auth_error(request, 401, "invalid_token", "Token validation failed")

        # 6. Store claims in request state
        request.state.jwt_claims = claims

        # 7. Extract principal from claims
        try:
            principal = _extract_principal(claims)
        except ValueError as exc:
            return self._auth_error(request, 401, "invalid_claims", str(exc))

        # 8. Set principal context and continue to next handler
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
        """Build RFC 7807 + RFC 6750 compliant error response.

        Args:
            request: Current request (for instance path and logging).
            status_code: HTTP status code (401, 403, or 503).
            error_code: Machine-readable error code (snake_case).
            message: Human-readable error description.

        Returns:
            JSONResponse with problem details and WWW-Authenticate header
            (for 401).
        """
        logger.info(
            "auth_validation_failed",
            extra={
                "error_code": error_code,
                "path": request.url.path,
                "method": request.method,
            },
        )

        headers: dict[str, str] = {}
        if status_code == 401:
            headers["WWW-Authenticate"] = (
                f'Bearer realm="API", error="{error_code}", error_description="{message}"'
            )

        _title_map = {
            401: "Unauthorized",
            403: "Forbidden",
            503: "Service Unavailable",
        }

        return JSONResponse(
            status_code=status_code,
            content={
                "type": f"/errors/{error_code.replace('_', '-')}",
                "title": _title_map.get(status_code, "Error"),
                "status": status_code,
                "detail": message,
                "error_code": error_code.upper(),
                "instance": str(request.url.path),
            },
            media_type=_PROBLEM_MEDIA_TYPE,
            headers=headers,
        )


def _extract_principal(claims: dict[str, Any]) -> Principal:
    """Extract Principal from validated JWT claims.

    Maps JWT claims to a frozen Principal value object. Validates
    required claims (sub, tenant_id) and coerces optional claims
    (roles, email, principal_type) to expected types.

    Args:
        claims: Decoded JWT claims dict.

    Returns:
        Principal value object.

    Raises:
        ValueError: If required claims are missing or malformed.
    """
    sub = claims.get("sub")
    if not sub:
        raise ValueError("JWT missing required claim: sub")

    try:
        user_id = UUID(str(sub))
    except (ValueError, AttributeError):
        raise ValueError(  # noqa: B904
            f"JWT 'sub' claim is not a valid UUID: {sub}"
        )

    tenant_id = claims.get("tenant_id", "")
    if not tenant_id:
        raise ValueError("JWT missing required claim: tenant_id")

    roles = claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]

    email = claims.get("email")
    principal_type_str = claims.get("principal_type", "user")

    return Principal(
        subject=str(sub),
        tenant_id=str(tenant_id),
        user_id=user_id,
        roles=tuple(roles),
        email=str(email) if email is not None else None,
        principal_type=(
            PrincipalType(principal_type_str)
            if principal_type_str in ("user", "agent")
            else PrincipalType.USER
        ),
    )


contribution = MiddlewareContribution(
    middleware_class=JWTAuthMiddleware,
    priority=150,  # Security band (100-199)
)
