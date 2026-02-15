# Framework Extraction Research: Composable Python Packages from Mnemonic

Research and feasibility analysis for extracting Mnemonic's architecture into a suite of composable, reusable Python packages.

---

## 1. What Exists Today (Inventory of Extractable Assets)

### 1A. Foundation / Domain Primitives (`shared/domain/`)

| Asset | Location | Dependencies | Extractability |
|-------|----------|-------------|----------------|
| `BaseAggregate` | `shared/domain/aggregates.py` | `eventsourcing.domain.Aggregate` | **High** — thin wrapper, generic |
| `BaseEvent` | `shared/events/base.py` | `eventsourcing.domain.DomainEvent` | **High** — adds tenant_id, correlation_id, user_id |
| `DomainError` hierarchy | `shared/domain/exceptions.py` | None (pure Python) | **High** — zero deps, fully generic |
| Identifier VOs (`TenantId`, `UserId`) | `shared/domain/identifiers.py` | None (pure Python) | **High** |
| `Principal` VO | `shared/domain/principal.py` | None (pure Python) | **High** |
| Port protocols (`LLMServicePort`) | `shared/domain/ports/` | `pydantic.BaseModel` (for TypeVar bound) | **High** |

### 1B. Application Layer Patterns (`shared/application/`)

| Asset | Location | Dependencies | Extractability |
|-------|----------|-------------|----------------|
| `Application[UUID]` wrappers | `shared/application/__init__.py`, `memory/application.py` | `eventsourcing.application` | **High** — pattern is generic |
| `TenantConfigService` | `shared/application/config_service.py` | Pure Python + domain types | **Medium** — config key/value types are Mnemonic-specific |
| `ResourceLimitService` | `shared/application/resource_limits.py` | Pure Python + domain types | **Medium** — pattern generic, config coupling |
| Policy binding service | `shared/application/policy_binding.py` | Pure Python + domain types | **Medium** |

### 1C. Infrastructure Layer (`shared/infrastructure/`)

| Asset | Location | Dependencies | Extractability |
|-------|----------|-------------|----------------|
| `EventStoreFactory` | `shared/infrastructure/persistence/event_store.py` | `eventsourcing[postgres]`, Pydantic | **High** |
| `BaseProjection` + runner/rebuilder | `shared/infrastructure/projections/` | `eventsourcing.system.ProcessApplication` | **High** |
| RFC 7807 error handlers | `shared/infrastructure/error_handlers.py` | FastAPI, domain exceptions | **High** — very reusable |
| Request context (`ContextVar` stack) | `shared/infrastructure/context.py` | None (stdlib `contextvars`) | **High** |
| Middleware stack | `shared/infrastructure/middleware/` | FastAPI/Starlette | **High** — each is independent |
| Auth (JWKS, JWT, PKCE, FusionAuth) | `shared/infrastructure/auth/` | PyJWT, httpx | **High** |
| Tenant context handler (RLS bridge) | `shared/infrastructure/persistence/tenant_context.py` | SQLAlchemy, context module | **High** |
| DB session/engine factories | `shared/infrastructure/dependencies/database.py` | SQLAlchemy, FastAPI | **High** |
| Feature flag dependency | `shared/infrastructure/dependencies/feature_flags.py` | FastAPI, domain types | **Medium** |
| Resource limit dependency | `shared/infrastructure/dependencies/resource_limits.py` | FastAPI, SQLAlchemy | **Medium** |
| LLM adapters (PydanticAI, Mock) | `shared/infrastructure/adapters/` | pydantic-ai | **High** |
| Config cache (L1 hybrid) | `shared/infrastructure/config_cache.py` | Pure Python | **Medium** |
| Observability (structlog + OTel) | `shared/observability/` | structlog, opentelemetry | **High** |
| TaskIQ broker config | `shared/infrastructure/taskiq.py` | taskiq, taskiq-redis | **High** |
| Alembic RLS migration helpers | `migrations/helpers/rls.py` | Alembic, SQLAlchemy | **High** |

### 1D. Enforced Architectural Constraints (`pyproject.toml`)

| Constraint | Mechanism | Extractability |
|------------|-----------|----------------|
| Bounded context independence | `import-linter` independence contract | **High** — parameterizable |
| Pure domain layer | `import-linter` forbidden contract | **High** — standard pattern |
| Shared kernel layering | `import-linter` layers contract | **High** |
| Strict mypy | `tool.mypy` strict config | **High** |
| Ruff lint/format rules | `tool.ruff` config | **High** |

### 1E. Domain Packages (candidates for reusable domains)

| Domain | Location | Notes |
|--------|----------|-------|
| Tenant lifecycle (state machine) | `shared/domain/tenant.py` | Multi-tenant provisioning/suspension/decommission |
| User provisioning (OIDC) | `shared/infrastructure/user_provisioning.py` | OIDC sub registry + profile |
| Agent identity & API keys | `shared/domain/agent.py`, `shared/application/agent_app.py` | Agent registration, API key issuance |
| Config/feature flags | `shared/domain/config_value_objects.py`, `shared/application/config_service.py` | Per-tenant config resolution chain |

---

## 2. Proposed Package Taxonomy

Inspired by .NET ABP Framework's modularity and Spring Boot's starter pattern, adapted for Python + uv workspaces.

### Layer 0: Foundation (zero framework deps)

```
praecepta-foundation-domain/     # Pure Python domain primitives
├── base_aggregate.py            # BaseAggregate (depends on eventsourcing.domain only)
├── base_event.py                # BaseEvent with tenant_id, correlation, causation, user
├── exceptions.py                # DomainError hierarchy (NotFound, Validation, Conflict, Auth...)
├── identifiers.py               # TenantId, UserId, generic typed ID base
├── principal.py                 # Principal VO (subject, tenant, roles)
├── ports/                       # Protocol interfaces (LLMServicePort, etc.)
└── value_objects.py             # Reusable VOs (Email, Money, Slug, etc.)

praecepta-foundation-application/ # Application layer patterns
├── base_application.py          # Generic Application[UUID] with snapshotting
├── base_handler.py              # Command/Query handler protocol
└── base_service.py              # Service base with tenant-scoped operations
```

**Dependencies:** `eventsourcing>=9.5`, `pydantic>=2.0` — these are arterial, not abstracted away.

### Layer 1: Infrastructure Packages (adapter implementations)

```
praecepta-infra-fastapi/         # FastAPI integration
├── error_handlers.py            # RFC 7807 ProblemDetail handlers
├── middleware/                   # RequestId, RequestContext, TraceContext, TenantState, Auth
├── dependencies/                # DB session, feature flags, resource limits (generic)
├── lifespan.py                  # Composable lifespan helpers
└── openapi.py                   # OpenAPI customization utilities

praecepta-infra-eventsourcing/   # Event store + projections
├── event_store_factory.py       # EventStoreFactory (Postgres)
├── config.py                    # EventSourcingSettings (Pydantic)
├── projections/                 # BaseProjection, runner, rebuilder
├── transcoders/                 # Custom transcoder base
└── postgres_parser.py           # DATABASE_URL parser

praecepta-infra-auth/            # Authentication adapters
├── jwks.py                      # JWKS provider
├── jwt_validator.py             # JWT validation
├── pkce.py                      # PKCE flow helpers
├── fusionauth_client.py         # FusionAuth adapter
├── auth_middleware.py           # AuthMiddleware (extracts Principal)
└── api_key_auth.py              # API key authentication middleware

praecepta-infra-persistence/     # Database infrastructure
├── tenant_context.py            # RLS bridge (SQLAlchemy → SET app.current_tenant)
├── session_factory.py           # Async/Sync session factories
├── rls_helpers.py               # Alembic migration helpers for RLS
└── redis.py                     # Redis client factory + settings

praecepta-infra-observability/   # Logging + tracing
├── logging.py                   # structlog config + sensitive data processor
├── tracing.py                   # OpenTelemetry config + shutdown
├── instrumentation.py           # Span helpers, traced_operation decorator
└── middleware.py                # TraceContextMiddleware

praecepta-infra-taskiq/          # Background task processing
├── broker.py                    # TaskIQ broker factory
└── fastapi_integration.py       # taskiq-fastapi init helper
```

### Layer 2: Domain Packages (reusable bounded contexts)

```
praecepta-domain-tenancy/        # Multi-tenant lifecycle
├── domain/
│   ├── tenant.py                # Tenant aggregate (state machine)
│   ├── value_objects.py         # TenantSlug, TenantName, TenantStatus
│   └── exceptions.py            # Tenant-specific errors
├── application/
│   ├── provision_tenant.py      # Provisioning handler
│   ├── suspend_tenant.py        # Suspension handler
│   └── config_service.py        # Per-tenant config resolution
├── infrastructure/
│   ├── projections/             # Tenant config projection, tenant usage
│   ├── slug_registry.py         # Unique slug reservation
│   └── tenant_state_cache.py    # Active/suspended cache
└── slices/                      # Pre-built vertical slices (optional)

praecepta-domain-identity/       # User + Agent identity
├── domain/
│   ├── user.py                  # User aggregate
│   ├── agent.py                 # Agent aggregate
│   └── value_objects.py         # UserProfile VOs, AgentCapabilities
├── application/
│   ├── user_app.py              # User application service
│   ├── agent_app.py             # Agent application service
│   └── provisioning.py          # OIDC provisioning service
└── infrastructure/
    ├── oidc_sub_registry.py     # OIDC subject → user mapping
    ├── user_profile_repo.py     # User profile read model
    └── agent_api_key_repo.py    # API key storage + hashing
```

**Future domain packages** (not yet implemented in Mnemonic but planned):

- `praecepta-domain-billing/` — Subscription, usage metering, payment integration
- `praecepta-domain-notifications/` — Notification channels, delivery, templates
- `praecepta-domain-audit/` — Audit log projections, compliance reporting

### Layer 3: Integration Packages (ACL / cross-domain glue)

```
praecepta-integration-tenancy-identity/
├── sagas/
│   ├── tenant_provisioned_creates_admin.py   # When tenant provisioned → create admin user
│   └── tenant_decommissioned_deletes_users.py
├── subscriptions/
│   └── user_provisioned_updates_tenant_count.py
└── acl.py                       # Type translations between Tenancy ↔ Identity

praecepta-integration-tenancy-billing/   # Future
├── sagas/
│   └── tenant_activated_creates_subscription.py
└── acl.py
```

**Key insight:** Integration packages depend on *two or more* domain packages and contain the sagas, process managers, and event subscriptions that cross bounded context boundaries. This keeps each domain package pure and independently testable.

**Second consumer:** A concrete second project exists and will validate the framework alongside Mnemonic.

---

## 3. Package Management Strategy

### Monorepo with uv Workspaces

```
praecepta/
├── pyproject.toml               # Workspace root
├── packages/
│   ├── foundation-domain/
│   │   ├── pyproject.toml       # name = "praecepta-foundation-domain"
│   │   └── src/praecepta/foundation/domain/
│   ├── foundation-application/
│   │   ├── pyproject.toml       # depends on praecepta-foundation-domain
│   │   └── src/praecepta/foundation/application/
│   ├── infra-fastapi/
│   │   ├── pyproject.toml       # depends on praecepta-foundation-domain + fastapi
│   │   └── src/praecepta/infra/fastapi/
│   ├── domain-tenancy/
│   │   ├── pyproject.toml       # depends on foundation-domain + foundation-application
│   │   └── src/praecepta/domain/tenancy/
│   └── ...
├── tests/                       # Cross-package integration tests
└── examples/
    └── starter-app/             # Minimal app composing foundation + infra-fastapi + domain-tenancy
```

**Namespace packages:** Use `praecepta.*` PEP 420 implicit namespace packages so all packages share the `praecepta` root without `__init__.py` conflicts.

**Registry:** Private GitHub Packages registry. Published via GitHub Actions CI/CD.

**Version strategy:** Independent versioning per package. Foundation packages use semver strictly. Infrastructure packages pin to compatible foundation versions.

### Dependency Graph

```
                praecepta-foundation-domain          ← Layer 0 (eventsourcing + pydantic)
                         │
                praecepta-foundation-application     ← Layer 0
                    ╱    │    ╲
                   ╱     │     ╲
praecepta-infra-fastapi  │  praecepta-infra-eventsourcing  ← Layer 1 (framework adapters)
praecepta-infra-auth     │  praecepta-infra-persistence
praecepta-infra-obs      │  praecepta-infra-taskiq
                   ╲     │     ╱
                    ╲    │    ╱
            praecepta-domain-tenancy                  ← Layer 2 (reusable domains)
            praecepta-domain-identity
                    ╱    ╲
                   ╱      ╲
praecepta-integration-tenancy-identity                ← Layer 3 (cross-domain glue)
```

---

## 4. Feasibility Assessment

### High Feasibility (can extract now)

| Component | Reason |
|-----------|--------|
| **Domain primitives** (BaseAggregate, BaseEvent, exceptions, identifiers) | Already pure Python + eventsourcing only. Zero Mnemonic-specific coupling. |
| **RFC 7807 error handlers** | Generic domain exception → HTTP response mapping. No business logic. |
| **Middleware stack** | Each middleware is independent and parameterized. |
| **Event store factory** | Wraps eventsourcing library; config is already Pydantic-based. |
| **Projection base + runner** | Generic ProcessApplication wrapper. |
| **Observability stack** | structlog + OTel setup is fully configurable. |
| **Request context (ContextVar)** | Zero dependencies, pure stdlib pattern. |

### Medium Feasibility (needs some generalization)

| Component | Challenge |
|-----------|-----------|
| **Tenant aggregate** | Config keys/values are Mnemonic-specific. Need to make config schema pluggable. |
| **Config service** | Resolution chain is generic, but `ConfigKey` enum is project-specific. Needs generic key registry. |
| **Auth middleware** | Tightly coupled to FusionAuth claim structure. Need to make claim extraction pluggable. |
| **RLS tenant context** | Pattern is generic, but the `app.current_tenant` variable name is hardcoded. Make configurable. |
| **Resource limits** | SQL queries are Mnemonic-specific. Need pluggable count providers. |
| **Import-linter contracts** | Template generation needed; can't just copy pyproject.toml. |

### Lower Feasibility (significant refactoring needed)

| Component | Challenge |
|-----------|-----------|
| **Vertical slices** | The slice structure (cmd.py, handler.py, endpoint.py) is a *pattern*, not extractable code. Best served by a cookiecutter/copier template + docs. |
| **Memory domain** | Inherently Mnemonic-specific. Not a candidate for extraction. |
| **Application factory (main.py)** | Composition root is always project-specific. Provide a reference + starter template. |

---

## 5. Design Decisions (Resolved)

### 5A. Naming & Branding

**Decision:** `praecepta` — Latin for "precepts" / "foundational rules." All packages use the `praecepta-*` prefix (e.g., `praecepta-foundation-domain`). Python namespace root: `praecepta.*`.

### 5B. Golden-Thread Technologies — No Abstraction

**Decision:** `eventsourcing` (both the pattern and the library), `FastAPI`, `Pydantic`, `SQLAlchemy`, `structlog`, and `OpenTelemetry` are **arterial** to the system. These are first-class dependencies, not things to abstract behind protocol layers.

- The framework *embraces* these libraries rather than wrapping them.
- Foundation packages depend directly on `eventsourcing>=9.5` and `pydantic>=2.0`.
- Infrastructure packages depend directly on `fastapi`, `sqlalchemy`, etc.
- **Risk acceptance:** If `eventsourcing` stalls, we fork/maintain rather than swap. The thin inheritance layer (BaseAggregate, BaseEvent) still provides a migration seam if needed — but we do not pre-invest in portability abstractions.

### 5C. Multi-Tenancy — Always On

**Decision:** Every aggregate, event, and infrastructure component is multi-tenant by default. A "single-tenant" application is simply a multi-tenant system with one tenant configured.

- `tenant_id` remains required on `BaseAggregate` and `BaseEvent`.
- RLS, tenant context propagation, and tenant-scoped queries are always active.
- Single-tenant deployments use a default tenant (e.g., `"default"` slug) created at bootstrap.
- **Rationale:** The overhead is minimal, and designing for multi-tenancy from the start pays off in maintainability. Retrofitting tenancy is far more expensive than having it unused.

### 5D. Integration Package Granularity

**Decision:** Fine-grained. One package per domain pair (`praecepta-integration-tenancy-identity`). Each integration has a clear dependency pair and can be omitted when not needed. Matches the composability goal.

### 5E. Convention Over Configuration — Auto-Discovery via Entry Points

**Decision:** Packages self-register their contributions. Installing a package is sufficient to activate it — no manual wiring required. This uses Python's standard **entry points** mechanism (PEP 621), the same pattern used by pytest plugins, Flask extensions, and OpenTelemetry instrumentors.

**How it works:** Each package declares what it provides in its `pyproject.toml`:

```toml
# praecepta-domain-tenancy/pyproject.toml
[project.entry-points."praecepta.routers"]
tenancy = "praecepta.domain.tenancy.api:router"

[project.entry-points."praecepta.projections"]
tenant_config = "praecepta.domain.tenancy.infrastructure.projections:TenantConfigProjection"

[project.entry-points."praecepta.applications"]
tenancy = "praecepta.domain.tenancy.application:TenantApplication"
```

```toml
# praecepta-integration-tenancy-identity/pyproject.toml
[project.entry-points."praecepta.subscriptions"]
tenant_identity = "praecepta.integration.tenancy_identity:register"
```

The framework provides a `create_app()` factory that discovers and wires everything:

```python
# praecepta.infra.fastapi.app_factory
from importlib.metadata import entry_points

def create_app(**settings) -> FastAPI:
    app = FastAPI(lifespan=_lifespan)

    # Auto-discover and register routers
    for ep in entry_points(group="praecepta.routers"):
        app.include_router(ep.load())

    # Auto-discover and register middleware
    for ep in entry_points(group="praecepta.middleware"):
        app.add_middleware(ep.load())

    # Auto-discover projections for event processing
    for ep in entry_points(group="praecepta.projections"):
        register_projection(ep.load())

    # Auto-discover integration subscriptions/sagas
    for ep in entry_points(group="praecepta.subscriptions"):
        ep.load()()  # Call the register function

    return app
```

**Entry point groups:**

- `praecepta.routers` — FastAPI APIRouter instances (auto-included)
- `praecepta.middleware` — ASGI middleware classes (auto-added in declared order)
- `praecepta.applications` — eventsourcing Application classes (auto-registered with system)
- `praecepta.projections` — BaseProjection subclasses (auto-wired to event store)
- `praecepta.subscriptions` — Registration functions from integration packages (sagas, event handlers)
- `praecepta.error_handlers` — Exception handler registrations
- `praecepta.lifespan` — Startup/shutdown hooks

**Consumer app remains minimal:**

```python
# myproject/main.py
from praecepta.infra.fastapi import create_app

app = create_app(
    title="My App",
    event_store_url="postgresql://...",
)
# That's it. All installed praecepta packages auto-register.
```

**Override/disable:** Consumers can exclude specific entry points or provide explicit configuration to override auto-discovery when needed (e.g., `exclude_groups=["praecepta.subscriptions"]` for testing).

**Why now:** This defines the fundamental **package contract** — how each package declares its contributions. Designing this in Phase 1 means every package follows the same pattern from day one. Retrofitting auto-discovery later would require touching every package's `pyproject.toml` and refactoring every consumer's `main.py`.

---

## 6. Extraction Strategy (Phased)

### Phase 1: Extract Foundation + Infrastructure (4-6 weeks)

1. ~~Create `praecepta` monorepo skeleton with uv workspaces + GitHub Actions CI.~~ ✅ — See [progress report](./progress.md#step-1--monorepo-scaffold-).
2. ~~Build auto-discovery infrastructure (`create_app()` factory, entry point group registry, discovery helpers).~~ ✅ — See [progress report](./progress.md#step-2--auto-discovery-infrastructure-).
3. ~~Extract `praecepta-foundation-domain` (aggregates, events, exceptions, identifiers, ports).~~ ✅ — See [progress report](./progress.md#step-3--praecepta-foundation-domain-).
4. ~~Extract `praecepta-foundation-application` (application base, handler protocols).~~ ✅ — See [progress report](./progress.md#step-4--praecepta-foundation-application-additions-).
5. ~~Extract `praecepta-infra-eventsourcing` (event store factory, projections, config) — with `praecepta.applications` + `praecepta.projections` entry points.~~ ✅ — See [progress report](./progress.md#step-5--praecepta-infra-eventsourcing-).
6. ~~Extract `praecepta-infra-fastapi` (error handlers, middleware, dependencies, `create_app()` factory) — with `praecepta.routers` + `praecepta.middleware` + `praecepta.error_handlers` discovery.~~ ✅ — See [progress report](./progress.md#step-6--praecepta-infra-fastapi-additions-).
7. ~~Extract `praecepta-infra-persistence` (session factories, RLS helpers, tenant context).~~ ✅ — See [progress report](./progress.md#step-7--praecepta-infra-persistence-).
8. ~~Extract `praecepta-infra-observability` (structlog + OTel) — with `praecepta.lifespan` entry point.~~ ✅ — See [progress report](./progress.md#step-8--praecepta-infra-observability-).
9. ~~Extract `praecepta-infra-auth` (JWT, JWKS, PKCE, auth middleware) — with `praecepta.middleware` entry point.~~ ✅ — See [progress report](./progress.md#step-9--praecepta-infra-auth-).
10. ~~Write comprehensive tests; validate with a minimal "dog school" example app that uses **only `create_app()` + installed packages** (zero manual wiring).~~ ✅ — See [progress report](./progress.md#step-10--integration-tests--example-app-).

> **Checkpoint 1:** All Layer 0 + Layer 1 packages published to GitHub Packages. Example app runs.

### Phase 2: Back-port Core into Mnemonic (2-3 weeks)

1. Replace `mnemonic.shared.domain.*` imports with `praecepta.foundation.domain.*`.
2. Replace `mnemonic.shared.events.*` imports with `praecepta.foundation.domain.*`.
3. Replace `mnemonic.shared.infrastructure.*` imports with corresponding `praecepta.infra.*` packages.
4. Remove extracted code from Mnemonic's `shared/` — keep only Mnemonic-specific application code.
5. Full test suite passes (unit, integration, e2e).
6. Import-linter contracts updated to reference `praecepta.*` namespaces.

> **Checkpoint 2:** Mnemonic runs on praecepta foundation + infrastructure. All tests green.

### Phase 3: Extract Domain Packages (3-4 weeks)

1. Generalize and extract `praecepta-domain-tenancy` (Tenant aggregate, config service, projections).
2. Generalize and extract `praecepta-domain-identity` (User, Agent, OIDC provisioning).
3. Create `praecepta-integration-tenancy-identity` (cross-domain sagas/subscriptions).
4. Write domain-package tests; validate with example app.

> **Checkpoint 3:** Domain packages published. Back-port into Mnemonic — replace remaining `mnemonic.shared` domain code with `praecepta.domain.*`. All tests green.

### Phase 4: Second Project Validation (3-4 weeks)

1. Bootstrap second project using praecepta packages.
2. Identify and resolve any missing generalization or rough edges.
3. Feed improvements back into praecepta packages.

> **Checkpoint 4:** Two independent projects consuming praecepta. Framework APIs stabilized.

### Phase 5: Developer Experience (2-3 weeks)

1. Create `copier` / `cookiecutter` project template that scaffolds a new app.
2. Import-linter contract templates (generated per bounded context).
3. Documentation site (seed from `_kb/domains/` content).
4. CI/CD finalized: GitHub Packages publishing, automated compatibility tests.
5. `praecepta-infra-taskiq` extracted (background task processing).

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Premature abstraction | High | Framework becomes complex before proving value | Start with exact extraction, generalize only when second project consumes it |
| eventsourcing lib abandonment | Low | Foundation packages become unmaintained | Thin wrapper allows migration; pin to known-good version |
| Namespace package conflicts | Medium | Import resolution issues in consumer projects | Comprehensive CI testing with editable installs + published packages |
| Scope creep (too many packages) | Medium | Maintenance burden | Strict criteria: extract only when ≥2 projects need it |
| Breaking changes propagation | Medium | Consumer projects break on updates | Independent versioning, strict semver, automated compatibility tests |

---

## 8. Comparable Ecosystem Precedents

| Ecosystem | Key Lesson for Us |
|-----------|------------------|
| **.NET ABP Framework** | Module = domain + application + infrastructure layers. Uses `IModule` interface for registration. We can use Python entry points similarly. |
| **Spring Boot Starters** | Auto-configuration via convention. We use Pydantic Settings for the same effect. |
| **Django ecosystem** | Namespace packages (django-rest-framework, django-tenants). Proven model for Python. |
| **NestJS Modules** | Decorator-based DI composition. Our FastAPI Depends() already serves this role. |
| **Python eventsourcing examples** | John Bywater's "dog school" pattern already demonstrates bounded context composition. Our `_kb/` docs are derived from this. |

**Key gap in Python ecosystem:** No production-scale DDD/ES framework exists in Python. The closest are fragmented libraries (lato, cosmos, pythonddd). This is a genuine opportunity.

---

## 9. Deferred: Knowledge Base Distribution (Separate Plan Needed)

**Problem:** The `_kb/` folder contains architecture patterns, conventions, ADRs, and domain briefs that describe *how to build on praecepta*. This knowledge must be accessible to AI coding agents in consuming projects — not just in the praecepta repo itself.

**Initial thinking on approaches:**

- **A) `praecepta-kb` package with static markdown + local MCP server.** The knowledge base ships as a Python package. Consuming projects install it and add the bundled MCP server to their `.mcp.json`. Agents query patterns/conventions contextually. Simplest to implement; version-locked to framework version.
- **B) Hosted MCP server backed by Neon + AuraDB.** Ingest `_kb/` into vector DB (pgvector/Neon for semantic search) and graph DB (AuraDB/Neo4j for relationship queries). Expose via a hosted MCP server. Richer querying, but adds infrastructure and a service to maintain.
- **C) Hybrid: static package for offline + hosted service for enriched queries.** Ship the markdown in a package for basic access; optionally connect to a hosted service for semantic/graph queries.

**Recommendation:** Start with **Option A** (ship as a package with local MCP) during Phase 1-2. Evaluate whether hosted enrichment (Option B/C) is needed once the second project validates the framework. This avoids premature infrastructure investment while still making the knowledge accessible.

**Key consideration:** The `_kb/` content will need to be split — some docs are praecepta-generic (DDD patterns, event sourcing conventions, multi-tenancy patterns) and some are Mnemonic-specific (memory domain briefs, ingestion patterns). The generic docs move to praecepta; Mnemonic-specific docs stay.

> **Action:** Create a separate plan for knowledge base distribution before Phase 2 back-port begins.

---

## 10. Open Questions

All design decisions resolved. No remaining open questions.
