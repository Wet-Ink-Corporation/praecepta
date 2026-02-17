<!-- Derived from {Project} PADR-116-jwt-auth-jwks -->
# PADR-116: JWT Authentication with JWKS Discovery

**Status:** Proposed
**Date:** 2026-02-06
**Deciders:** Architecture Team
**Categories:** Pattern, Security, Infrastructure
**Proposed by:** docs-enricher (feature F-102-001)

---

## Context

{Project} requires user authentication for all API endpoints except health checks and documentation. The authentication system must:

- Integrate with an external OIDC provider for centralized identity management
- Validate RS256-signed JWTs on every request with minimal latency
- Extract custom claims (`tenant_id`, `roles`) for authorization and multi-tenancy
- Support automatic key rotation without downtime
- Allow local development without running identity provider infrastructure
- Propagate authenticated identity to endpoint handlers via dependency injection

### Alternatives Considered

| Alternative | Rejected Why |
|-------------|-------------|
| **Session-based auth** | Stateful, doesn't scale horizontally, no SSO |
| **Symmetric HS256 JWTs** | Shared secret, no key rotation, can't use OIDC provider |
| **Opaque tokens** | Requires token introspection endpoint (adds latency), can't extract claims locally |
| **OAuth2 Password Grant** | Deprecated, less secure than authorization code flow, {Project} API doesn't handle passwords |
| **Custom JWKS fetcher (httpx)** | Duplicates logic in PyJWT's PyJWKClient, no clear benefit |
| **Full OIDC discovery** | Extra startup network call, standard OIDC providers follow standard JWKS path |

### Technology Selection

| Technology | Purpose | Version |
|------------|---------|---------|
| **PyJWT** | JWT decode/validation, RS256 support | 2.8+ |
| **PyJWKClient** (bundled with PyJWT) | JWKS fetching and caching | 2.8+ |
| **cryptography** | RS256 signature verification | 41.0+ (via pyjwt[crypto]) |

**Rationale for PyJWT:**

- Industry standard (45M+ downloads/month)
- Native RS256 support via `cryptography` library
- Built-in `PyJWKClient` for JWKS caching with kid-based refresh
- Active maintenance and security fixes

**Rationale for PyJWKClient:**

- Handles TTL-based caching (default: 300s)
- Automatic kid mismatch → refresh → retry on key rotation
- Thread-safe for concurrent requests
- Uses synchronous HTTP (urllib) - acceptable for ~300s refresh interval

### Custom Claims Contract

OIDC provider JWT payload:

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  // UUID, required
  "tenant_id": "acme-corp",                        // Custom, required
  "roles": ["admin", "editor"],                    // Custom, optional (default: [])
  "email": "user@example.com",                     // Standard, optional
  "principal_type": "user",                        // Custom, optional (default: "user")
  "iss": "https://auth.example.com",              // Standard, required
  "aud": "{Project}-api",                          // Standard, required
  "exp": 1735689600,                               // Standard, required
  "iat": 1735686000                                // Standard, required
}
```

## Decision

### 1. Use RS256 JWT with JWKS Discovery

All API requests (except excluded paths) MUST include a valid `Authorization: Bearer <token>` header with an RS256-signed JWT issued by the OIDC provider. JWT signatures are verified using public keys cached from the provider's JWKS endpoint (`/.well-known/jwks.json`).

### 2. JWKSProvider as Lifespan Singleton

Create a `JWKSProvider` singleton during FastAPI lifespan startup and store in `app.state`. The provider:

- Constructs JWKS URI from issuer URL (`{issuer}/.well-known/jwks.json`)
- Wraps PyJWT's `PyJWKClient` with 300s TTL
- Handles kid mismatch → refresh automatically

### 3. AuthMiddleware with BaseHTTPMiddleware

Use `BaseHTTPMiddleware` (not pure ASGI) for consistency with existing middleware stack. Middleware flow:

1. Check if path is excluded (e.g., `/health`, `/docs`)
2. Check dev bypass (if enabled and no Authorization header)
3. Extract Bearer token from Authorization header
4. Fetch signing key from JWKSProvider (cache hit or JWKS refresh)
5. Validate JWT signature and standard claims (exp, iss, aud, sub)
6. Extract custom claims to typed `Principal` value object
7. Set principal in `_principal_context` ContextVar
8. Call next middleware/handler
9. Clear principal context in finally block

### 4. Principal as Frozen Domain Value Object

Map JWT claims to a `Principal` frozen dataclass in the domain layer:

```python
@dataclass(frozen=True, slots=True)
class Principal:
    subject: str           # JWT 'sub' claim
    tenant_id: str         # Custom 'tenant_id' claim
    user_id: UUID          # Parsed from 'sub'
    roles: tuple[str, ...] # Custom 'roles' claim
    email: str | None      # Standard 'email' claim
    principal_type: PrincipalType  # Custom claim (USER|AGENT)
```

**Rationale:**

- Domain-pure (no external dependencies, import-linter compliant)
- Immutable (frozen=True, thread-safe)
- Type-safe (UUID validation on extraction)

### 5. Separate Principal ContextVar

Use `_principal_context: ContextVar[Principal | None]` instead of extending `RequestContext` dataclass. This avoids breaking the frozen `RequestContext` contract and allows independent lifecycle management by `AuthMiddleware`.

### 6. FastAPI Dependency Injection

Provide `get_current_principal()` and `require_role()` dependencies for endpoint handlers:

```python
from {Project}.shared.infrastructure.auth.dependencies import CurrentPrincipal, require_role

@router.post("/blocks")
def create_block(principal: CurrentPrincipal, cmd: CreateBlockCommand):
    # principal.tenant_id, principal.user_id, principal.roles available
    ...

@router.delete("/admin/purge")
def admin_purge(
    _: Annotated[None, Depends(require_role("admin"))],
    principal: CurrentPrincipal,
):
    # Only principals with "admin" role can reach this handler
    ...
```

### 7. Development Bypass with Production Lockout

Allow local development without an identity provider via `AUTH_DEV_BYPASS=true`. Safety rules:

- **Production lockout**: `{Project}_ENV=production` ALWAYS blocks bypass
- **Explicit opt-in**: Bypass is disabled by default
- **Header-absent only**: If Authorization header is present, validate normally (even in dev mode)
- **Structured logging**: WARNING when active, ERROR when blocked

Synthetic claims:

```python
DEV_BYPASS_CLAIMS = {
    "sub": "00000000-0000-0000-0000-000000000000",  # Nil UUID
    "tenant_id": "dev-tenant",
    "roles": ["admin"],
    # ... obviously non-production values
}
```

### 8. RFC 7807 + RFC 6750 Error Responses

All 401 responses MUST include:

- RFC 7807 Problem Details JSON body
- RFC 6750 WWW-Authenticate header with error and error_description

Example:

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/problem+json
WWW-Authenticate: Bearer realm="{Project} API", error="invalid_token", error_description="Token has expired"

{
  "type": "/errors/token-expired",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Token has expired",
  "error_code": "TOKEN_EXPIRED",
  "instance": "/api/v1/blocks"
}
```

### 9. Middleware Stack Position

```
Request → RequestIdMiddleware → TraceContextMiddleware → **AuthMiddleware**
        → RequestContextMiddleware → TenantStateMiddleware → CORS → Route
```

**Critical:**

- **After RequestId/Trace**: Correlation ID and trace spans available for auth error logging
- **Before RequestContext**: Principal extraction happens before request context is set
- **Before TenantState**: Tenant from JWT claim validated before tenant suspension check

### 10. Path Exclusions

Excluded from JWT validation:

- `/health` — Kubernetes liveness/readiness probes
- `/docs`, `/openapi.json`, `/redoc`, `/scalar` — API documentation
- `/favicon` — Browser favicon requests

NOT excluded:

- `/api/v1/tenants` — Admin tenant management endpoints (require authentication)

## Consequences

### Positive

- **Zero database calls per request** — JWT validation uses cached public keys, no session lookup
- **Horizontal scalability** — Stateless authentication, no shared session store
- **Automatic key rotation** — PyJWKClient handles kid mismatch → refresh transparently
- **Type-safe principal** — Frozen dataclass prevents bugs from claim typos or type mismatches
- **Development velocity** — Dev bypass enables local dev without identity provider infrastructure
- **Standards compliance** — RFC 7519 (JWT), RFC 6750 (Bearer), RFC 7807 (Problem Details), OIDC Discovery
- **Tenant isolation** — `tenant_id` in JWT ensures every request is tenant-scoped

### Negative

- **Key rotation delay** — Up to 300s delay before new keys are cached (JWKS TTL)
- **Blocking HTTP on key refresh** — PyJWKClient uses synchronous urllib (brief blocking every ~300s)
- **OIDC provider coupling** — Assumes the OIDC provider's custom claims structure (`tenant_id`, `roles`)
- **UUID-only subjects** — OIDC provider `sub` must be a valid UUID (email-based subjects would fail)
- **Dev bypass risk** — Accidental production bypass would be a critical security issue (mitigated by lockout)
- **No revocation** — JWTs cannot be revoked (mitigation: short expiry, e.g., 1 hour)

### Neutral

- **BaseHTTPMiddleware overhead** — ~0.1ms per request vs pure ASGI (negligible vs ~1-3ms JWT validation)
- **Separate ContextVar** — Two ContextVars (request_context + principal_context) vs one unified context
- **No OIDC discovery** — Assumes standard JWKS path (can add override if needed)

## Migration Path

This is the **first authentication implementation** in {Project}. No migration needed.

Future enhancements (not in scope for F-102-001):

- **F-102-002**: Add Authorization Code Flow with PKCE for web console
- **F-102-003**: Add JIT user provisioning from OIDC claims
- **F-102-004**: Add API key authentication for agents (separate middleware)

## Implementation Notes

- **Feature:** F-102-001 JWT Validation Middleware
- **Stories:** S-102-001-001 (JWKS), S-102-001-002 (Middleware), S-102-001-003 (Principal), S-102-001-004 (Dev Bypass), S-102-001-005 (Integration Tests)
- **Key files:**
  - `src/{Project}/shared/infrastructure/auth/jwks.py` — JWKSProvider
  - `src/{Project}/shared/infrastructure/middleware/auth.py` — AuthMiddleware + _extract_principal
  - `src/{Project}/shared/domain/principal.py` — Principal value object
  - `src/{Project}/shared/infrastructure/context.py` — Principal ContextVar
  - `src/{Project}/shared/infrastructure/auth/dependencies.py` — FastAPI deps
  - `src/{Project}/shared/infrastructure/auth/dev_bypass.py` — Production lockout

## Related

- [ref-infra-jwt-auth-middleware.md](../../domains/security/references/ref-infra-jwt-auth-middleware.md) — JWT middleware pattern
- [ref-infra-jwks-provider.md](../../domains/security/references/ref-infra-jwks-provider.md) — JWKS provider pattern
- [ref-infra-dev-bypass-safety.md](../../domains/security/references/ref-infra-dev-bypass-safety.md) — Dev bypass safety pattern
- [ref-domain-principal.md](../../domains/security/references/ref-domain-principal.md) — Principal value object
- [PADR-109: Sync-First Event Sourcing](PADR-109-sync-first-eventsourcing.md) — Middleware async strategy
- [PADR-110: Application Lifecycle](PADR-110-application-lifecycle.md) — Lifespan singleton pattern
- [PADR-103: Error Handling Strategy](PADR-103-error-handling.md) — RFC 7807 pattern, AuthenticationError/AuthorizationError hierarchy
- [PADR-106: Configuration Management](PADR-106-configuration.md) — Pydantic settings for auth config
