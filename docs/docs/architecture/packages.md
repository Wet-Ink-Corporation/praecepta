# Packages

Praecepta is a uv workspaces monorepo. All packages live under `packages/` and share the `praecepta.*` namespace via [PEP 420 implicit namespace packages](namespace-packages.md).

## Package Map

### Layer 0: Foundation

| Package | Namespace | Purpose |
|---------|-----------|---------|
| `praecepta-foundation-domain` | `praecepta.foundation.domain` | Pure domain primitives: identifiers, exceptions, events, aggregates, value objects, config types, ports |
| `praecepta-foundation-application` | `praecepta.foundation.application` | Application patterns: request context, contribution types, discovery utility, policy/config/limit services |

**Foundation packages have zero external framework dependencies.** They define the vocabulary (types, protocols, exceptions) that all other layers use.

### Layer 1: Infrastructure

| Package | Namespace | Purpose |
|---------|-----------|---------|
| `praecepta-infra-fastapi` | `praecepta.infra.fastapi` | `create_app()` factory, middleware, error handling, settings |
| `praecepta-infra-eventsourcing` | `praecepta.infra.eventsourcing` | Event store factory, `BaseProjection`, config cache |
| `praecepta-infra-auth` | `praecepta.infra.auth` | JWT/JWKS, API key auth, PKCE, OIDC, dev bypass |
| `praecepta-infra-persistence` | `praecepta.infra.persistence` | PostgreSQL sessions, Redis, Row-Level Security helpers |
| `praecepta-infra-observability` | `praecepta.infra.observability` | Structured logging, distributed tracing, health checks |
| `praecepta-infra-taskiq` | `praecepta.infra.taskiq` | Background task queue integration |

### Layer 2: Domain

| Package | Namespace | Purpose |
|---------|-----------|---------|
| `praecepta-domain-tenancy` | `praecepta.domain.tenancy` | Tenant aggregate and application service |
| `praecepta-domain-identity` | `praecepta.domain.identity` | User and Agent aggregates and application services |

### Layer 3: Integration

| Package | Namespace | Purpose |
|---------|-----------|---------|
| `praecepta-integration-tenancy-identity` | `praecepta.integration.tenancy_identity` | Cross-domain coordination between tenancy and identity |

## Key Exports by Package

### `praecepta.foundation.domain`

The most commonly used imports:

```python
from praecepta.foundation.domain import (
    # Identifiers
    TenantId, UserId,
    # Base types
    BaseAggregate, BaseEvent,
    # Exceptions
    DomainError, ValidationError, ConflictError, NotFoundError,
    # Value objects
    TenantName, TenantSlug, Email, DisplayName,
    # Ports
    APIKeyGeneratorPort, LLMServicePort,
    # Security
    Principal, PrincipalType,
)
```

### `praecepta.foundation.application`

```python
from praecepta.foundation.application import (
    # Request context
    RequestContext, get_current_context,
    get_current_tenant_id, get_current_principal,
    # Contributions (for entry-point registration)
    MiddlewareContribution, LifespanContribution,
    ErrorHandlerContribution, DiscoveredContribution,
    # Discovery
    discover,
)
```

### `praecepta.infra.fastapi`

```python
from praecepta.infra.fastapi import (
    create_app,              # App factory — discovers and wires everything
    AppSettings,             # Configuration for the app factory
    ProblemDetail,           # RFC 7807 error response format
)
```
