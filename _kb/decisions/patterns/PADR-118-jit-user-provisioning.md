<!-- Derived from {Project} PADR-118-jit-user-provisioning -->
# PADR-118: JIT User Provisioning in Auth Middleware

**Status:** Proposed
**Date:** 2026-02-08
**Deciders:** Architecture Team
**Categories:** Pattern, Security
**Proposed by:** docs-enricher (feature F-102-003)

---

## Context

Feature F-102-003 (User Provisioning) introduced OIDC-based user authentication with an external OIDC provider. Users are authenticated externally via JWT validation, but do not exist in {Project}'s domain model until a User aggregate is created.

This creates a bootstrapping problem: the first authenticated request from a new user has a valid JWT with `oidc_sub` claim, but no corresponding User aggregate or `user_id` exists in the system.

### Requirements

1. **User aggregate required** — All resources, Processing jobs, and query sessions must be attributed to a `user_id` for audit trails and ownership
2. **Synchronous guarantee** — Request handlers must see a valid `user_id` in `Principal` before executing
3. **Idempotency** — Concurrent first-login requests for the same `oidc_sub` must not create duplicate users
4. **Non-blocking** — Authentication must not fail if user provisioning encounters a transient error (retry on next request)
5. **Performance** — Fast-path check for existing users must be <1ms (99.9% of requests)

### Alternatives Considered

| Approach | Rejection Reason |
|----------|------------------|
| **Manual provisioning** (admin creates users before first login) | Poor UX; adds friction; requires admin intervention for every new user |
| **Async provisioning** (fire-and-forget from middleware) | Eventual consistency gap: handler would see `user_id=None` on first request, causing 500 errors |
| **Pre-flight check in handlers** (each handler calls `ensure_user_exists()`) | Duplicated logic across 20+ endpoints; violates DRY; poor separation of concerns |
| **Database trigger** (auto-insert user row on Principal extraction) | Tight coupling to PostgreSQL; cannot use event sourcing for User aggregate |

---

## Decision

We integrate user provisioning directly into `AuthMiddleware` using a synchronous call to `UserProvisioningService.ensure_user_exists()` **after** JWT validation and **before** setting `principal_context`:

```python
# src/{Project}/shared/infrastructure/middleware/auth.py
async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
    # 1. Validate JWT and extract claims
    claims = self._validate_jwt(token)
    principal = self._extract_principal(claims)

    # 2. Ensure User aggregate exists (JIT provisioning)
    user_provisioning = getattr(request.app.state, "user_provisioning", None)
    if user_provisioning is not None:
        try:
            user_provisioning.ensure_user_exists(
                oidc_sub=principal.subject,
                tenant_id=principal.tenant_id,
                email=claims.get("email"),
                name=claims.get("name"),
            )
        except Exception:
            # Non-fatal: log and continue (user can retry on next request)
            logger.exception("user_provisioning_failed", extra={"oidc_sub": principal.subject})

    # 3. Set principal context for request handlers
    set_principal_context(principal)
    return await call_next(request)
```

### Fast-Path/Slow-Path Optimization

The `UserProvisioningService` uses a **fast-path/slow-path** strategy:

- **Fast-path (99.9% of requests):** Single indexed SELECT on `user_oidc_sub_registry.oidc_sub` (PRIMARY KEY) → return `user_id` (~0.1ms)
- **Slow-path (first login only):** Reserve → Create aggregate → Save → Confirm (~5-10ms)

### Non-Fatal Failure Handling

If provisioning fails (database unavailable, event store error), the exception is logged but **does not block authentication**. The user's JWT is still valid; they can retry on the next request.

Rationale: Temporary infrastructure failures should not break authentication for **existing** users. New users see a transient 500 error from handlers (missing `user_id`), but this self-heals on retry.

---

## Consequences

### Positive

- **Zero manual user creation** — seamless UX for first-time users
- **Synchronous guarantee** — handlers always see a valid `user_id` in `Principal` (no eventual consistency gap)
- **Idempotent** — concurrent first-login requests produce exactly one User aggregate (via three-phase reservation)
- **Fast-path dominates** — 99.9% of requests add <0.1ms overhead
- **Centralized logic** — all 20+ endpoints benefit without per-handler code

### Negative

- **Middleware coupling** — AuthMiddleware now depends on domain (User) and application (UserApplication) layers, violating strict hexagonal separation
- **First-login latency** — slow-path adds 5-10ms to first authenticated request per user
- **Non-fatal failure UX** — new users see cryptic 500 errors on transient provisioning failures (requires retry)
- **Hidden provisioning** — developers must understand that User aggregates are auto-created, not manually provisioned

### Neutral

- **Provisioning is synchronous** — PADR-109 permits sync operations in request path for commands; provisioning is a command (User.Provisioned event)
- **Registry table overhead** — Each user adds one row to `user_oidc_sub_registry` (~100 bytes), acceptable for 100k-1M users

---

## Implementation Notes

- **Feature:** F-102-003 User Provisioning
- **Key files:**
  - `src/{Project}/shared/infrastructure/middleware/auth.py` — JIT provisioning call (lines 256-266)
  - `src/{Project}/shared/infrastructure/user_provisioning.py` — Provisioning service
  - `src/{Project}/shared/infrastructure/oidc_sub_registry.py` — Three-phase reservation registry
  - `src/{Project}/shared/domain/user.py` — User aggregate
- **Pattern:** [ref-infra-jit-provisioning.md](../../domains/security/references/ref-infra-jit-provisioning.md)

---

## Related

- [PADR-109: Sync-First Event Sourcing](PADR-109-sync-first-eventsourcing.md) — Permits sync provisioning in request path
- [PADR-110: Application Lifecycle](PADR-110-application-lifecycle.md) — Lifespan-managed `UserApplication` singleton
- [PADR-116: JWT Auth JWKS](../strategic/PADR-116-jwt-auth-jwks.md) — JWT validation in AuthMiddleware
- [PADR-119: Separate UserApplication](PADR-119-separate-user-application.md) — Why User has its own Application
- [ref-infra-slug-reservation.md](../../domains/multi-tenancy/references/ref-infra-slug-reservation.md) — Three-phase reservation base pattern
