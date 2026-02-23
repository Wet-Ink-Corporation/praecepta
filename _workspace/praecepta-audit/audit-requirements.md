# Praecepta Infrastructure Audit Requirements

**Purpose:** Systematic framework for auditing whether praecepta's infrastructure packages correctly use their upstream libraries.
**Prompted by:** Projection infrastructure remediation (2026-02-22) — the redkiln team flagged one issue; investigation found three more in the same package.
**Complements:** Codebase Quality Audit (2026-02-18) which assessed code quality, testing, and documentation but not upstream library alignment.

---

## 1. Audit Objective

Praecepta's value proposition is convention-over-configuration that bakes best practices. If our infrastructure adapters misuse their upstream libraries, we are baking *anti-patterns* instead. This audit answers:

> **For each infrastructure package, are we using the upstream library the way its authors intended — and are we exposing sensible conventions to downstream consumers?**

Specifically, the audit seeks to identify:

- **Bypassed abstractions** — Using low-level APIs when the library provides purpose-built higher-level ones (e.g., `SingleThreadedRunner` + polling instead of `EventSourcedProjectionRunner` + LISTEN/NOTIFY)
- **Resource waste** — Connection pool explosion, unnecessary instances, polling where subscriptions exist
- **Incorrect wiring** — Broadcasting events to wrong consumers, misconfigured middleware ordering, wrong session scoping
- **Missing library features** — Reimplementing functionality the library already provides
- **Configuration anti-patterns** — Hardcoded values that should be configurable, defaults that don't match library recommendations
- **Lifecycle mismanagement** — Resources not cleaned up, startup/shutdown ordering issues

---

## 2. Scope

### 2.1 Packages Under Audit

| Package | Upstream Libraries | Risk | Prior Findings |
|---------|-------------------|------|----------------|
| `infra-eventsourcing` | `eventsourcing[postgres]` 9.5, `psycopg` 3.1, `cachetools` | **Audited** | 4 issues found and remediated (2026-02-22) |
| `infra-fastapi` | `fastapi` 0.115+, `starlette`, `pydantic-settings` | **High** | Complex middleware/lifespan/auto-discovery. No prior library-usage audit. |
| `infra-auth` | `pyjwt[crypto]` 2.8, `httpx` 0.28, `bcrypt` 4.0 | **High** | Security-critical. Incorrect usage = vulnerabilities. |
| `infra-persistence` | `sqlalchemy` 2.0, `alembic` 1.13, `redis` 5.0 | **High** | Connection pooling, session scoping, RLS. Resource-intensive. |
| `infra-observability` | `structlog` 24.0, `opentelemetry-api/sdk` 1.20 | **Medium** | Configuration correctness, context propagation. |
| `infra-taskiq` | `taskiq` 0.11, `taskiq-redis` 1.2 | **Medium** | Already flagged: bypasses all infra conventions (prior audit P1-06). |

### 2.2 What Is NOT In Scope

- Domain packages (Layer 2) and integration packages (Layer 3) — these consume infrastructure, they don't wrap upstream libraries
- Foundation packages (Layer 0) — `eventsourcing.Aggregate` usage is part of domain model quality (covered by prior audit Dimension 2)
- Code quality, test coverage, documentation — already covered by the 2026-02-18 audit

---

## 3. Audit Methodology

Adapted from the proven multi-pass agent pipeline (`_workspace/retrospective/methodology.md`, `_workspace/kb-audit/audit-plan.md`).

### 3.1 Pipeline Overview

```
Pass 1: 5 Collector agents (parallel) — per-package library usage analysis
    ↓ files on disk
Pass 2: 3 Theme agents (parallel) — cross-cutting concerns
    ↓ files on disk
Pass 3: 1 Synthesis agent — consolidated findings + severity ratings
    ↓ files on disk
Pass 4: 1 Remediation agent — prioritised fix list with verification criteria
```

Total: ~10 agents. Files on disk as handoff mechanism (fresh context per agent).

### 3.2 Pass 1: Per-Package Collectors

Each collector agent receives:
- The package's source code (all `.py` files under `src/`)
- The package's test files
- The package's `pyproject.toml` (for dependency versions)
- The relevant upstream library documentation (fetched via Context7 or web)
- The per-package checklist from Section 4

Each collector produces: `pass-1/{package-name}.md` containing:
- Checklist scores (Pass/Fail/Partial per item)
- Findings with severity, file path, line number
- Recommendations

| Agent | Package | Estimated Files |
|-------|---------|----------------|
| C-01 | infra-fastapi | ~15 source + ~10 test |
| C-02 | infra-auth | ~12 source + ~8 test |
| C-03 | infra-persistence | ~8 source + ~4 test |
| C-04 | infra-observability | ~6 source + ~3 test |
| C-05 | infra-taskiq | ~4 source + ~1 test |

`infra-eventsourcing` is excluded (already remediated) but its findings serve as the reference case.

### 3.3 Pass 2: Cross-Cutting Theme Agents

Each theme agent reads all Pass 1 outputs and focuses on one cross-cutting concern:

| Agent | Theme | Question |
|-------|-------|----------|
| T-01 | Resource Budget | What is the total connection/thread/memory budget across all packages? Are there runaway pools? |
| T-02 | Lifecycle Coherence | Do all packages follow the same startup/shutdown patterns? Are there ordering dependencies? |
| T-03 | Convention Compliance | Do all packages follow entry-point auto-discovery, Pydantic settings, and configuration layering? |

Each produces: `pass-2/{theme-name}.md`

### 3.4 Pass 3: Synthesis

One agent reads all Pass 1 and Pass 2 outputs. Produces: `pass-3/consolidated-findings.md` with:
- Findings table (ID, package, severity, description, file, recommendation)
- RAG status per package
- Cross-cutting themes narrative

### 3.5 Pass 4: Remediation Backlog

One agent reads the synthesis report. Produces: `pass-4/remediation-backlog.md` with:
- Priority-ordered fix list (P1/P2/P3)
- Effort estimates (S/M/L)
- Verification criteria for each item
- Dependency ordering (what must be fixed before what)

---

## 4. Per-Package Checklists

### 4.1 infra-fastapi (FastAPI 0.115+ / Starlette)

**Library API Usage (FA-1 through FA-6)**

- FA-1: `create_app()` uses FastAPI's lifespan protocol correctly (async context manager, not `on_event`)
- FA-2: Middleware is added via `app.add_middleware()` with correct LIFO ordering (outermost added last)
- FA-3: Error handlers use `@app.exception_handler()` or `add_exception_handler()` — not catching exceptions in middleware
- FA-4: Dependency injection uses `Depends()` with proper scoping (request-scoped vs app-scoped)
- FA-5: CORS middleware uses Starlette's `CORSMiddleware` with correct origin/method/header configuration
- FA-6: Router inclusion uses `include_router()` with appropriate `prefix` and `tags`

**Resource Management (FA-7 through FA-9)**

- FA-7: No global mutable state outside of lifespan-managed resources
- FA-8: Background tasks (if any) use FastAPI's `BackgroundTasks` or properly managed external task queue
- FA-9: TestClient usage in tests correctly manages lifespan (enters/exits async context)

**Configuration (FA-10 through FA-12)**

- FA-10: `AppSettings` follows Pydantic Settings best practices (`model_config`, `env_prefix`, validators)
- FA-11: Debug/development settings cannot accidentally leak into production
- FA-12: OpenAPI schema configuration is correct (title, version, docs URLs)

**Lifecycle Management (FA-13 through FA-15)**

- FA-13: Lifespan contributions compose correctly (startup order = priority ascending, shutdown = reverse)
- FA-14: Lifespan failures during startup abort cleanly (no half-initialized state)
- FA-15: Health check endpoint returns meaningful status (not just 200 OK)

**Middleware-Specific (FA-16 through FA-19)**

- FA-16: `RequestContextMiddleware` correctly populates and clears context vars per request
- FA-17: Middleware priority bands are documented and enforced (not just conventional)
- FA-18: Middleware handles WebSocket connections correctly (or explicitly excludes them)
- FA-19: Middleware handles exceptions without swallowing them or breaking the ASGI chain

### 4.2 infra-auth (PyJWT / httpx / bcrypt)

**Library API Usage (AU-1 through AU-6)**

- AU-1: JWT validation uses `jwt.decode()` with explicit `algorithms=["RS256"]` (not defaulting to `HS256`)
- AU-2: JWKS keys are cached with TTL and automatic refresh on key rotation (not fetched per-request)
- AU-3: `bcrypt` hashing uses appropriate work factor (12+ rounds, not default 4)
- AU-4: `httpx` client uses connection pooling (`httpx.AsyncClient` as singleton, not per-request instantiation)
- AU-5: Token claims validation checks `exp`, `iss`, `aud` — not just signature
- AU-6: PKCE implementation uses cryptographically secure random bytes (`secrets` module, not `random`)

**Security (AU-7 through AU-13)**

- AU-7: API key comparison uses constant-time comparison (`hmac.compare_digest`, not `==`)
- AU-8: JWT error handling does not leak key/algorithm information in error responses
- AU-9: Dev bypass mode is gated by explicit environment variable and cannot be accidentally enabled
- AU-10: OIDC discovery document is validated (issuer matches, endpoints use HTTPS)
- AU-11: Token refresh flows handle clock skew correctly
- AU-12: API key generation produces sufficient entropy (≥256 bits)
- AU-13: Auth middleware returns 401 (not 403) for missing/invalid credentials, 403 for insufficient permissions

**Resource Management (AU-14 through AU-15)**

- AU-14: `httpx.AsyncClient` is properly closed during shutdown (not leaked)
- AU-15: JWKS cache is bounded (won't grow unbounded with key rotations over time)

**Configuration (AU-16 through AU-17)**

- AU-16: `AuthSettings` validates JWKS URL format, issuer format
- AU-17: Sensitive settings (secrets, keys) are not logged or exposed via settings dump

### 4.3 infra-persistence (SQLAlchemy 2.0 / Alembic / Redis)

**Library API Usage (PE-1 through PE-7)**

- PE-1: Uses SQLAlchemy 2.0 style (`select()`, `Session.execute()`) not 1.x legacy (`session.query()`)
- PE-2: Engine creation uses `create_async_engine()` with appropriate pool parameters
- PE-3: Session factory uses `async_sessionmaker` (not `sessionmaker` with sync engine)
- PE-4: Sessions are scoped to request lifecycle (not module-level or global)
- PE-5: Alembic migrations use async engine support correctly
- PE-6: Redis client uses connection pooling (`redis.asyncio.Redis` with `ConnectionPool`)
- PE-7: RLS policy creation uses parameterized queries (no SQL injection via tenant ID)

**Resource Management (PE-8 through PE-12)**

- PE-8: Connection pool size is configurable and documented (not hardcoded)
- PE-9: Pool overflow settings are appropriate for the deployment model
- PE-10: `dispose_engine()` is called during shutdown (connections are actually released)
- PE-11: Redis connections are properly closed during shutdown
- PE-12: Total connection budget across all packages is documented and within PostgreSQL limits

**Configuration (PE-13 through PE-15)**

- PE-13: `DatabaseSettings` validates connection string format
- PE-14: Pool parameters (`pool_size`, `max_overflow`, `pool_timeout`) have documented defaults
- PE-15: `echo` flag (SQL logging) defaults to `False` and is only enabled in development

**Session Scoping (PE-16 through PE-18)**

- PE-16: No session sharing between concurrent requests
- PE-17: Sessions are committed/rolled back explicitly (not relying on garbage collection)
- PE-18: Nested transactions (savepoints) are used correctly if at all

### 4.4 infra-observability (structlog / OpenTelemetry)

**Library API Usage (OB-1 through OB-6)**

- OB-1: `structlog` is configured once at startup (not reconfigured per-request)
- OB-2: Context variables use `structlog.contextvars` (not thread-local or global dict)
- OB-3: OpenTelemetry SDK is configured with appropriate exporter (OTLP, not console in production)
- OB-4: Trace context propagation uses W3C Trace-Context format
- OB-5: Span creation follows OpenTelemetry naming conventions
- OB-6: `shutdown_tracing()` flushes pending spans before process exit

**Configuration (OB-7 through OB-9)**

- OB-7: Log level is configurable via environment variable
- OB-8: Tracing sample rate is configurable (not hardcoded to 100%)
- OB-9: Service name is set correctly in OpenTelemetry resource attributes

**Integration (OB-10 through OB-12)**

- OB-10: Request ID from middleware is included in structured log output
- OB-11: Trace context middleware is outermost (lowest priority number)
- OB-12: Log output format is appropriate for the deployment target (JSON for production, human-readable for dev)

### 4.5 infra-taskiq (TaskIQ / taskiq-redis)

**Library API Usage (TQ-1 through TQ-5)**

- TQ-1: Broker uses `ListQueueBroker` or `StreamQueueBroker` as recommended (not deprecated alternatives)
- TQ-2: Result backend is properly configured with TTL (results don't accumulate indefinitely)
- TQ-3: Task serialization uses appropriate format (JSON, not pickle for security)
- TQ-4: Scheduler uses TaskIQ's built-in scheduling (not a custom cron implementation)
- TQ-5: Worker startup/shutdown hooks are properly registered

**Convention Compliance (TQ-6 through TQ-9)**

- TQ-6: Uses `TaskIQSettings(BaseSettings)` with `env_prefix` (not hardcoded or `os.environ.get()`)
- TQ-7: Registers a `LifespanContribution` for broker lifecycle (not ad-hoc startup)
- TQ-8: Exposes broker as a singleton via entry-point (not module-level instantiation)
- TQ-9: Error handling follows the same patterns as other infrastructure packages

**Resource Management (TQ-10 through TQ-11)**

- TQ-10: Redis connections for task queue are separate from persistence Redis (or explicitly shared)
- TQ-11: Broker is properly shut down during application exit

---

## 5. Cross-Cutting Checklists

### 5.1 Resource Budget (XC-R1 through XC-R5)

- XC-R1: Total PostgreSQL connection count is documented (sum of: event store pool + read model pool + projection runners + Alembic)
- XC-R2: Total Redis connection count is documented (persistence cache + task queue + result backend)
- XC-R3: Background thread count is documented (projection runners + task workers + polling threads)
- XC-R4: No package creates unbounded resources (pools without max size, caches without eviction)
- XC-R5: Resource limits are appropriate for typical deployment (single-instance dev, multi-instance production)

### 5.2 Lifecycle Coherence (XC-L1 through XC-L5)

- XC-L1: All infrastructure resources are created in lifespan hooks (not at import time or first request)
- XC-L2: Startup ordering is correct (database before event store, event store before projections)
- XC-L3: Shutdown ordering is reverse of startup (projections before event store, event store before database)
- XC-L4: Startup failures in one package don't leave other packages in a half-initialized state
- XC-L5: Health checks reflect actual readiness (database connected, event store accessible, projections running)

### 5.3 Convention Compliance (XC-C1 through XC-C6)

- XC-C1: Every package with configurable behavior uses `BaseSettings` with `env_prefix`
- XC-C2: Every package with lifecycle requirements registers a `LifespanContribution`
- XC-C3: Every package exports its public API via `__init__.py` and `__all__`
- XC-C4: Every package follows PEP 420 implicit namespace conventions (no `__init__.py` in intermediate directories)
- XC-C5: Deprecated code has `DeprecationWarning` with migration guidance
- XC-C6: No package uses `os.environ` directly (all config via Pydantic Settings)

### 5.4 Async/Sync Model Consistency (XC-A1 through XC-A4)

- XC-A1: Commands (writes) are synchronous — event store operations are sync by design
- XC-A2: Queries (reads) are asynchronous — database reads use async sessions
- XC-A3: Projections are synchronous — event processing uses sync handlers
- XC-A4: No blocking sync calls in async contexts (no `time.sleep()` in async functions, no sync DB calls in async handlers)

### 5.5 Error Propagation (XC-E1 through XC-E3)

- XC-E1: Infrastructure errors are wrapped in domain-appropriate exceptions (not raw `SQLAlchemyError` leaking to API)
- XC-E2: Error handlers produce RFC 7807 Problem Detail responses consistently
- XC-E3: Transient errors (connection timeout, Redis unavailable) are distinguishable from permanent errors (invalid query, missing table)

---

## 6. Severity Classification

Aligned with the 2026-02-18 codebase quality audit for consistency.

| Severity | Definition | Example from Projection Remediation |
|----------|-----------|--------------------------------------|
| **CRITICAL** | Would cause data loss, security breach, or production outage | — (none found, but connection pool exhaustion under load would qualify) |
| **HIGH** | Resource waste, performance degradation, or incorrect behavior under load | `SingleThreadedRunner` creating N+1 app instances with 225 max connections |
| **HIGH** | Incorrect wiring that produces wrong results silently | All projections broadcast to all applications (wrong event routing) |
| **MEDIUM** | Anti-pattern that works but degrades performance or maintainability | Polling at 1s interval instead of LISTEN/NOTIFY (3,600 unnecessary queries/hour) |
| **LOW** | Cosmetic or minor deviation from best practice | `BaseProjection` extending `ProcessApplication` instead of lighter base class |

### Severity Decision Tree

```
Does it cause data loss, security breach, or outage?
  → Yes: CRITICAL
  → No: Could it cause resource exhaustion or incorrect behavior under load?
    → Yes: HIGH
    → No: Does it create unnecessary resource usage or maintenance burden?
      → Yes: MEDIUM
      → No: LOW
```

---

## 7. Output Specification

### 7.1 Per-Package Report (Pass 1)

```markdown
# {Package Name} — Library Usage Audit

**Upstream Library:** {library name and version}
**RAG Status:** {RED/AMBER/GREEN}
**Checklist:** {N}/{M} passed

## Findings

| ID | Severity | Checklist | Description | File:Line | Recommendation |
|----|----------|-----------|-------------|-----------|----------------|
| {pkg}-F01 | HIGH | FA-2 | Middleware added in wrong order | middleware.py:45 | Reverse addition order |

## Narrative
{Brief analysis of the package's library usage quality}
```

### 7.2 Cross-Cutting Theme Report (Pass 2)

```markdown
# {Theme Name} — Cross-Cutting Audit

## Findings

| ID | Severity | Packages Affected | Description | Recommendation |
|----|----------|-------------------|-------------|----------------|
| XC-F01 | HIGH | persistence, eventsourcing | Total pool budget exceeds PG default | Document and cap at 100 |

## Analysis
{How this theme manifests across packages}
```

### 7.3 Consolidated Findings (Pass 3)

```markdown
# Consolidated Audit Findings

## Summary
| Package | RAG | Critical | High | Medium | Low |
|---------|-----|----------|------|--------|-----|

## All Findings (sorted by severity)
{merged table from all Pass 1 + Pass 2 reports}

## Cross-Cutting Themes
{narrative from Pass 2 reports}
```

### 7.4 Remediation Backlog (Pass 4)

```markdown
# Remediation Backlog

## P1 — Fix Before Next Release
| ID | Finding | Package | Effort | Depends On | Verification |
|----|---------|---------|--------|------------|--------------|

## P2 — Fix Before Beta
| ... |

## P3 — Improvement Backlog
| ... |
```

---

## 8. Reference: Lessons from Projection Remediation

The following failure patterns were discovered during the 2026-02-22 eventsourcing audit. These patterns should be specifically checked for in all other packages.

### Pattern 1: Bypassing Purpose-Built Abstractions

**What happened:** Used `SingleThreadedRunner` (generic system runner) instead of `EventSourcedProjectionRunner` (purpose-built for projections).
**Root cause:** The library's recommended API was not discovered during initial implementation.
**Check for:** Are we using generic/low-level APIs where the library provides specialized ones?

### Pattern 2: N+1 Resource Multiplication

**What happened:** `SingleThreadedRunner` created one application instance per projection follower plus one leader instance, each with its own connection pool.
**Root cause:** Not understanding the resource implications of the chosen API.
**Check for:** Does our usage create more instances/connections/threads than necessary?

### Pattern 3: Incorrect Wiring via Convention Gap

**What happened:** `projection_lifespan.py` broadcast all projections to all applications instead of routing each projection to its declared upstream.
**Root cause:** No mechanism to associate projections with their upstream application.
**Check for:** Are our auto-discovery/wiring mechanisms routing to the correct targets?

### Pattern 4: Polling Where Subscriptions Exist

**What happened:** Used `time.sleep()`-based polling instead of PostgreSQL LISTEN/NOTIFY.
**Root cause:** Not discovering the library's subscription mechanism.
**Check for:** Are we polling where the library (or the database) provides push-based alternatives?

---

## 9. Execution Prerequisites

Before running the audit:

1. **Baseline verification:** `make verify` must pass (all tests green, zero lint/type/boundary issues)
2. **Library documentation access:** Agents need access to upstream library docs via Context7 or web fetch
3. **Output directory:** `_workspace/praecepta-audit/` with subdirectories `pass-1/`, `pass-2/`, `pass-3/`, `pass-4/`
4. **Reference materials:**
   - This document (`audit-requirements.md`)
   - Prior quality audit (`_workspace/retrospective/consolidated-report.md`)
   - Prior remediation backlog (`_workspace/retrospective/remediation-backlog.md`)
   - Projection remediation plan (`.claude/plans/vast-soaring-neumann.md`)
