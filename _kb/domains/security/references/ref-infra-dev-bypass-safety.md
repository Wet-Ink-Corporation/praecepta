# Development Bypass Safety Pattern

> Environment-based authentication bypass with production lockout and structured logging

**Feature:** F-102-001 | **Story:** S-102-001-004
**Category:** Infrastructure Pattern
**Last updated:** 2026-02-06

---

## Problem

Developers need to run the API locally without an identity provider instance by injecting a synthetic principal. However, this bypass is a critical security risk if accidentally enabled in production. The solution must:

- Allow explicit opt-in via environment variable (`{Project}_AUTH_DEV_BYPASS=true`)
- Block bypass in production environments regardless of configuration
- Log WARNING when bypass is active in development
- Log ERROR when bypass is requested but blocked in production
- Only bypass when `Authorization` header is absent (if a token is provided, validate it normally)

## Solution

A standalone `resolve_dev_bypass()` function that evaluates the bypass request against the current runtime environment, with production safety as the highest priority.

### Decision Flow

```mermaid
graph TD
    Start[resolve_dev_bypass requested?] -->|False| Disabled[Return False]
    Start -->|True| CheckEnv{{Project}_ENV?}
    CheckEnv -->|production| Block[Log ERROR<br/>Return False]
    CheckEnv -->|development, staging, local| Enable[Log WARNING<br/>Return True]

    Enable -.-> Middleware{Authorization header?}
    Middleware -->|Present| Validate[Normal JWT Validation]
    Middleware -->|Absent| Inject[Inject DEV_BYPASS_CLAIMS]
```

## Implementation

### Core Function

```python
# src/{project}/shared/infrastructure/auth/dev_bypass.py
import logging
import os

logger = logging.getLogger(__name__)

def resolve_dev_bypass(requested: bool) -> bool:
    """Resolve whether development authentication bypass should be active.

    Evaluates the bypass request against the current runtime environment.
    Production environments ALWAYS block bypass regardless of the request flag.

    Args:
        requested: Whether bypass was requested via {Project}_AUTH_DEV_BYPASS=true.

    Returns:
        True if bypass should be active, False otherwise.

    Side effects:
        - Logs WARNING when bypass is active in non-production environment.
        - Logs ERROR when bypass is requested but blocked in production.
    """
    if not requested:
        return False

    env = os.environ.get("{Project}_ENV", "development")

    if env == "production":
        logger.error(
            "auth_dev_bypass_blocked",
            extra={
                "environment": env,
                "detail": (
                    "Authentication bypass was requested but blocked in production environment."
                ),
            },
        )
        return False

    logger.warning(
        "auth_dev_bypass_active",
        extra={
            "environment": env,
            "detail": ("Authentication bypass is enabled. Do not use in production."),
        },
    )
    return True
```

### Middleware Integration

```python
# src/{project}/shared/infrastructure/middleware/auth.py
from {project}.shared.infrastructure.auth.dev_bypass import resolve_dev_bypass

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, jwks_provider, issuer, audience, dev_bypass: bool):
        super().__init__(app)
        # Production safety check happens during initialization
        self._dev_bypass = resolve_dev_bypass(dev_bypass)
        # ...

    async def dispatch(self, request, call_next):
        auth_header = request.headers.get("Authorization", "")

        # Bypass only applies when NO Authorization header is present
        if self._dev_bypass and not auth_header:
            from {project}.shared.infrastructure.auth import DEV_BYPASS_CLAIMS
            claims = dict(DEV_BYPASS_CLAIMS)
            principal = _extract_principal(claims)
            # ... inject principal and continue

        # If Authorization header is present, normal validation runs (even in dev mode)
        # ...
```

### Synthetic Claims Constants

```python
# src/{project}/shared/infrastructure/auth/__init__.py
DEV_BYPASS_CLAIMS: dict[str, object] = {
    "sub": "00000000-0000-0000-0000-000000000000",  # Nil UUID
    "tenant_id": "dev-tenant",
    "roles": ["admin"],
    "email": "dev-bypass@localhost",
    "iss": "dev-bypass",
    "aud": "{app}-api",
    "exp": 0,  # Sentinel: bypass never "expires" in dev mode
}
```

## When to Use

Use this pattern when:

- Building authentication middleware for external identity providers
- Need local development without running identity provider infrastructure
- Want explicit opt-in for insecure modes (not implicit defaults)
- Need production safety checks to prevent configuration leakage

## When NOT to Use

Do NOT use this pattern when:

- Authentication is optional (public endpoints) — use path exclusion instead
- Using test fixtures for authentication — use proper mocks in tests
- Production environment needs special auth modes — use feature flags, not bypass

## Trade-offs

| Pro | Con |
|-----|-----|
| Enables local development without identity provider | Bypass is a security risk if leaked to production |
| Explicit opt-in (default: bypass disabled) | Developers must remember to set `{Project}_AUTH_DEV_BYPASS=true` |
| Production lockout prevents accidents | No way to override lockout (intentional) |
| Structured logging aids debugging | Logs WARNING on every startup (noisy) |
| Validates tokens when present (even in dev mode) | Cannot test token validation errors in dev bypass mode |

## Safety Mechanisms

### 1. Production Lockout

```python
if env == "production":
    logger.error("auth_dev_bypass_blocked")
    return False
```

**Rationale:** Production is defined as `{Project}_ENV=production`. No configuration override can enable bypass in production.

### 2. Explicit Request

Bypass is NOT enabled by default. Must set `{Project}_AUTH_DEV_BYPASS=true`.

### 3. Header-Absent Only

```python
if self._dev_bypass and not auth_header:
    # Inject synthetic claims
```

If an `Authorization: Bearer <token>` header is present, normal JWT validation runs even when bypass is enabled. This prevents bypass from masking token format errors during development.

### 4. Startup Logging

```
WARNING: auth_dev_bypass_active {"environment": "development", "detail": "..."}
```

Logs at WARNING level on every startup when bypass is active, making it visible in logs.

### 5. Non-Production-Like Claims

```python
"sub": "00000000-0000-0000-0000-000000000000",  # Nil UUID
"tenant_id": "dev-tenant",  # Obviously non-production
```

Synthetic claims use clearly non-production values to prevent confusion.

## Configuration

Environment variables:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `{Project}_AUTH_DEV_BYPASS` | bool | `false` | Enable dev bypass (opt-in) |
| `{Project}_ENV` | str | `development` | Runtime environment (`development`, `staging`, `production`) |

Pydantic settings:

```python
# src/{project}/shared/infrastructure/config/auth.py
class AuthSettings(BaseSettings):
    dev_bypass: bool = Field(
        default=False,
        description="Skip JWT validation in development",
    )
```

## Error Scenarios

| Scenario | Behavior |
|----------|----------|
| `dev_bypass=true` + `{Project}_ENV=production` | Blocked, ERROR log, return False |
| `dev_bypass=false` + any environment | Disabled, no log, return False |
| `dev_bypass=true` + `{Project}_ENV=development` | Enabled, WARNING log, return True |
| `dev_bypass=true` + Authorization header present | Normal JWT validation (bypass skipped) |
| `dev_bypass=true` + Authorization header absent | Inject `DEV_BYPASS_CLAIMS` |

## Testing

### Unit Test Patterns

```python
def test_dev_bypass_blocked_in_production(monkeypatch):
    monkeypatch.setenv("{Project}_ENV", "production")
    assert resolve_dev_bypass(requested=True) is False

def test_dev_bypass_enabled_in_development(monkeypatch):
    monkeypatch.setenv("{Project}_ENV", "development")
    assert resolve_dev_bypass(requested=True) is True

def test_dev_bypass_disabled_when_not_requested():
    assert resolve_dev_bypass(requested=False) is False

def test_dev_bypass_skipped_when_auth_header_present(test_client):
    # Even with bypass enabled, providing a token triggers validation
    response = test_client.get("/api/v1/blocks", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401  # Not bypassed, validation ran
```

## Related

- [JWT Authentication Middleware Pattern](ref-infra-jwt-auth-middleware.md) — Uses resolve_dev_bypass() for bypass decision
- [JWKS Provider Pattern](ref-infra-jwks-provider.md) — Skipped when dev bypass is active
- [PADR-106: Configuration Management](../../decisions/patterns/PADR-106-configuration.md) — Environment variable patterns
- [PADR-116: JWT Authentication with JWKS Discovery](../../decisions/patterns/PADR-116-jwt-auth-jwks.md) — Dev bypass as part of auth strategy

## See Also

- `src/{project}/shared/infrastructure/auth/dev_bypass.py` — Full implementation
- `src/{project}/shared/infrastructure/middleware/auth.py` — Middleware integration
- `src/{project}/shared/infrastructure/auth/__init__.py` — DEV_BYPASS_CLAIMS constants
