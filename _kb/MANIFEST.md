# Praecepta Knowledge Base

> NAVIGATION PROTOCOL: Read this manifest first. Load domain briefs by keyword match.
> Only load Tier 2 references when a brief's Reference Index directs you to.
> NEVER load all files — always navigate via this index.

## Domains

| Domain | Brief | Scope |
|--------|-------|-------|
| ddd-patterns | `domains/ddd-patterns/BRIEF.md` | Aggregates, value objects, vertical slices, events, hexagonal architecture |
| event-store-cqrs | `domains/event-store-cqrs/BRIEF.md` | Event store, projections, PostgreSQL, transcoder, CQRS |
| multi-tenancy | `domains/multi-tenancy/BRIEF.md` | Request context, RLS, tenant config, feature flags |
| api-framework | `domains/api-framework/BRIEF.md` | FastAPI routes, DTOs, error handling, middleware, auto-discovery, app factory |
| security | `domains/security/BRIEF.md` | Auth (JWT, JWKS, OIDC), authorization (ReBAC), tenant isolation |
| observability | `domains/observability/BRIEF.md` | Logging, tracing, metrics, health checks |
| test-strategy | `domains/test-strategy/BRIEF.md` | Testing patterns, fixtures, testcontainers, coverage |
| infrastructure | `domains/infrastructure/BRIEF.md` | PostgreSQL, Redis, Neo4j, Docker, configuration |
| deployment | `domains/deployment/BRIEF.md` | Docker Compose, migrations, CI/CD |

## Cross-Cutting Constraints

| Constraint | Description |
|------------|-------------|
| import-boundaries | Enforced via lint-imports; domain layer has zero external dependencies |
| async-strategy (PADR-109) | Commands use sync `def`, queries use `async def`, projections sync |
| multi-tenancy | RLS on all tables; tenant_id required on all projections |
| event-sourcing | Immutable append-only; state derived from event replay |

## Collections

| Collection | Index | Description |
|------------|-------|-------------|
| decisions | `decisions/_index.md` | 25 PADRs (4 strategic + 21 pattern) |
| design | `design/BRIEF.md` | Development process, governance, agent pipeline patterns |

## Tools

| Tool | Path | Purpose |
|------|------|---------|
| search-index | `SEARCH_INDEX.md` | Cross-domain concept lookup — load before broad search |
