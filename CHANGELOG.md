## v2.0.0 (2026-02-28)

### BREAKING CHANGE

- BaseProjection.policy() is renamed to process_event(). Projection
constructors now require a view parameter. ProjectionRunner and ProjectionPoller
classes are removed — use SubscriptionProjectionRunner instead.

### Fix

- migrate projections from ProcessApplication to Projection to fix connection pool exhaustion

## v1.0.0 (2026-02-23)

### BREAKING CHANGE

- Middleware classes are now pure ASGI (no longer extend
BaseHTTPMiddleware). The /healthz endpoint returns a richer JSON payload
with per-subsystem status. MiddlewareContribution default priority changed
from 500 to 400 (max is now 499). New lifespan hooks (persistence, auth,
taskiq) are auto-discovered and must be excluded in test fixtures that
don't have external services available.

### Fix

- infrastructure audit remediation — 42 findings across 8 phases

## v0.3.0 (2026-02-18)

### Fix

- replace in-process projection runner with polling-based consumption

## v0.2.0 (2026-02-18)

### Feat

- add projection runner auto-discovery lifespan hook
