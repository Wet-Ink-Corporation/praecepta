# Praecepta

Composable Python framework for building DDD/ES multi-tenant applications.

## Packages

| Package | Layer | Description |
|---------|-------|-------------|
| `praecepta-foundation-domain` | 0 | Pure Python domain primitives (aggregates, events, exceptions, identifiers) |
| `praecepta-foundation-application` | 0 | Application layer patterns (base application, handler protocols) |
| `praecepta-infra-fastapi` | 1 | FastAPI integration (error handlers, middleware, app factory) |
| `praecepta-infra-eventsourcing` | 1 | Event store factory, projections, config |
| `praecepta-infra-auth` | 1 | JWT, JWKS, PKCE, auth middleware |
| `praecepta-infra-persistence` | 1 | Session factories, RLS helpers, tenant context |
| `praecepta-infra-observability` | 1 | structlog + OpenTelemetry logging and tracing |
| `praecepta-infra-taskiq` | 1 | TaskIQ background task processing |
| `praecepta-domain-tenancy` | 2 | Multi-tenant lifecycle management |
| `praecepta-domain-identity` | 2 | User and agent identity management |
| `praecepta-integration-tenancy-identity` | 3 | Cross-domain sagas between tenancy and identity |

## Quickstart

```bash
# Clone and install
git clone <repo-url> && cd praecepta
uv sync --dev

# Run verification
make verify
```

## Development

```bash
make test           # Run all tests
make lint           # Lint with auto-fix
make format         # Format code
make typecheck      # Strict mypy
make boundaries     # Check architecture boundaries
make verify         # All of the above
```

## Architecture

- **uv workspaces** monorepo with independent package versioning
- **PEP 420** implicit namespace packages under `praecepta.*`
- **Layered dependency graph:** Foundation → Infrastructure → Domain → Integration
- **Convention over configuration** via Python entry points for auto-discovery