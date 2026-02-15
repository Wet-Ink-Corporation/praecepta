<!-- Derived from {Project} PADR-120-multi-auth-middleware-sequencing -->
# PADR-120: Multi-Auth Middleware Sequencing (First-Match-Wins)

**Status:** Proposed
**Date:** 2026-02-08
**Context:** F-102-004 Agent Identity (S-102-004-003)
**Domain:** security, api-framework
**Type:** Pattern Decision

---

## Context

{Project} supports multiple authentication mechanisms for different client types:
- **Human users** authenticate via JWT tokens (OIDC/OAuth2 flows with external OIDC provider)
- **Machine clients** (agents, services, cron jobs) authenticate via API keys (X-API-Key header)
- **Future:** Internal services may use mTLS certificates, legacy clients may require HMAC signatures

When multiple auth mechanisms are supported, the API must decide:
1. **Which mechanism to use** when client sends multiple headers (e.g., both X-API-Key and Authorization)
2. **How to structure validation logic** (unified middleware vs separate middlewares)
3. **How to avoid fallback chains** (e.g., "try API key, if fails try JWT") that weaken security

**Prior art:**
- F-102-001 implemented JWT-only authentication via `AuthMiddleware` (PADR-116)
- F-102-004 adds API key authentication via `APIKeyAuthMiddleware`
- Design decision DD-F4-2 chose separate middlewares (not unified middleware with switch statement)

**Design alternatives considered:**
1. **Unified AuthMiddleware with switch statement** — Check for X-API-Key, if present validate API key, else check for Authorization: Bearer, if present validate JWT
2. **Header priority flags (X-Prefer-Auth)** — Client sends both headers + preference flag, middleware honors preference
3. **First-match-wins via separate middlewares** — Each middleware checks for its header, first to set principal context wins
4. **All-mechanisms validation** — If both headers present, validate both and fail if either is invalid

---

## Decision

**Implement each authentication mechanism as a separate middleware** with **first-match-wins** semantics via shared `Principal` ContextVar.

**Sequencing rule:**
- Middlewares execute in **LIFO registration order** (last added = first executed)
- First middleware to **set principal context** wins
- Later middlewares **check for existing principal** and skip validation if already set

**Implementation pattern:**

```python
# Middleware 1: API key auth (runs FIRST)
class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Check if principal already set by earlier middleware (defensive)
        if get_optional_principal() is not None:
            return await call_next(request)

        # 2. Extract X-API-Key header
        if not request.headers.get("X-API-Key"):
            # No API key -> delegate to next middleware
            return await call_next(request)

        # 3. Validate API key OR return 401 (fail-fast)
        # 4. Set principal context and continue

# Middleware 2: JWT auth (runs SECOND)
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 0. Check if principal already set by APIKeyMiddleware (first-match-wins)
        if get_optional_principal() is not None:
            return await call_next(request)

        # 1. Extract Authorization: Bearer header
        # 2. Validate JWT OR return 401 (fail-fast)
        # 3. Set principal context and continue

# Application startup (LIFO order: last added = first executed)
app.add_middleware(AuthMiddleware, ...)     # Runs 2nd
app.add_middleware(APIKeyAuthMiddleware)    # Runs 1st (added last)
```

**Order guarantee:** API key authentication runs BEFORE JWT authentication. If `X-API-Key` header is present, API key wins (JWT validation skipped).

---

## Rationale

**Why first-match-wins (not fallback chain)?**
- **Security:** Fallback chains (try API key, if fails try JWT) weaken security by accepting weaker credentials
- **Simplicity:** Client controls which auth to use via header presence (no need for priority flags)
- **Fail-fast:** Invalid credentials return 401 immediately (no silent fallback to different mechanism)

**Why separate middlewares (not unified with switch statement)?**
- **Single Responsibility Principle:** Each middleware handles one auth mechanism
- **Testability:** Each middleware can be unit tested in isolation
- **Extensibility:** Adding new auth mechanisms requires one new middleware, no changes to existing ones
- **Minimal modification:** Existing `AuthMiddleware` only needs one check (if principal already set, skip)

**Why ContextVar as contract (not request.state)?**
- **Existing pattern:** `Principal` is already stored in ContextVar (F-102-001)
- **Thread-safe:** ContextVar is safer for async context propagation than request.state
- **Consistency:** All auth middlewares use same contract (`set_principal_context()`)

---

## Consequences

### Positive

1. **Clean separation of concerns** — Each middleware handles one auth mechanism
2. **Extensible** — Adding OAuth2 client credentials or mTLS requires one new middleware
3. **Testable** — Each middleware can be unit tested in isolation
4. **Fail-fast** — Invalid credentials return 401 immediately (no silent fallback)
5. **Client controls auth mechanism** — Client sends relevant header (X-API-Key or Authorization), middleware responds accordingly

### Negative

1. **Middleware ordering is critical** — Misconfiguration (wrong registration order) silently breaks first-match-wins
2. **Shared ContextVar contract** — All auth middlewares must use `Principal` ContextVar (cannot use different auth models)
3. **First-match-wins may surprise users** — If client sends both headers, API key wins (no validation of JWT)

### Neutral

1. **Manual registration order** — Middlewares must be added in correct order at application startup (documented in main.py)
2. **Principal check in every middleware** — Each middleware must check `get_optional_principal()` before proceeding

---

## Alternatives Considered

### Alternative 1: Unified AuthMiddleware with Switch Statement

```python
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check for X-API-Key first
        if request.headers.get("X-API-Key"):
            # Validate API key
            pass
        # Check for Authorization: Bearer
        elif request.headers.get("Authorization"):
            # Validate JWT
            pass
        else:
            return 401
```

**Rejected because:**
- Violates Single Responsibility Principle (one middleware handles multiple auth mechanisms)
- Hard to test (must mock both API key and JWT validation in same test)
- Not extensible (adding mTLS requires modifying existing middleware)
- Complex branching (if/elif/else chains grow with each new mechanism)

---

### Alternative 2: Header Priority Flags (X-Prefer-Auth)

```python
# Client sends both headers + preference
headers = {
    "X-API-Key": "mne_...",
    "Authorization": "Bearer ...",
    "X-Prefer-Auth": "api-key"  # Client preference
}

# Middleware honors preference
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        preference = request.headers.get("X-Prefer-Auth", "jwt")
        if preference == "api-key":
            # Validate API key
        else:
            # Validate JWT
```

**Rejected because:**
- Unnecessary complexity (client already controls via header presence)
- Requires custom header (non-standard)
- Doesn't solve ordering problem (still need to decide which validates first if both present)

---

### Alternative 3: All-Mechanisms Validation

```python
# If both headers present, validate BOTH
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        api_key = request.headers.get("X-API-Key")
        jwt = request.headers.get("Authorization")

        if api_key and jwt:
            # Validate both, fail if either is invalid
            validate_api_key(api_key)  # Raises if invalid
            validate_jwt(jwt)          # Raises if invalid
            # Both valid -> use API key principal (arbitrary choice)
```

**Rejected because:**
- Expensive (2x validation cost for clients that send both headers)
- Doesn't add security (if API key is valid, JWT validation is redundant)
- Still requires arbitrary choice (which principal to use if both valid?)

---

## Implementation Notes

### Middleware Registration Order (Critical)

From `src/{Project}/main.py`:

```python
# CRITICAL: Middleware registration is LIFO (last added = first executed)
# Order: RequestId -> APIKey -> Auth -> TenantState -> CORS -> Routes

app.add_middleware(TenantStateMiddleware)  # Runs 3rd
app.add_middleware(AuthMiddleware, ...)    # Runs 2nd (JWT)
app.add_middleware(APIKeyAuthMiddleware)   # Runs 1st (API key, added last)
app.add_middleware(RequestIdMiddleware)    # Runs 0th (outermost)
```

**Error-prone:** If `APIKeyAuthMiddleware` is added BEFORE `AuthMiddleware`, JWT validation runs first (API key loses).

**Mitigation:** Document middleware ordering in main.py comments. Consider meta-test to verify middleware order.

---

### Principal Context Contract

All auth middlewares MUST:
1. Call `get_optional_principal()` at the start of `dispatch()`
2. Skip validation if principal already set (first-match-wins)
3. Set principal context via `set_principal_context(principal)` after successful validation
4. Clear principal context in `finally` block

**Example (from APIKeyAuthMiddleware):**

```python
async def dispatch(self, request: Request, call_next: Callable) -> Response:
    # 1. Check if principal already set
    if get_optional_principal() is not None:
        return await call_next(request)

    # 2. Extract and validate credentials
    # ...

    # 3. Set principal context
    principal_token = set_principal_context(principal)
    try:
        return await call_next(request)
    finally:
        clear_principal_context(principal_token)
```

---

## Related Decisions

- [PADR-116 JWT Auth JWKS](PADR-116-jwt-auth-jwks.md) — JWT validation (first auth mechanism)
- [PADR-121 Projection-Based Authentication](PADR-121-projection-based-authentication.md) — API key lookup via projection
- [PADR-103 Error Handling](PADR-103-error-handling.md) — RFC 7807 error responses for 401

---

## References

- Feature: F-102-004 Agent Identity (S-102-004-003)
- Pattern: [ref-infra-multi-auth-middleware.md](../../domains/security/references/ref-infra-multi-auth-middleware.md)
- Implementation: `src/{Project}/shared/infrastructure/middleware/api_key_auth.py`
- Implementation: `src/{Project}/shared/infrastructure/middleware/auth.py` (modified for first-match-wins)

---

**End of ADR**
