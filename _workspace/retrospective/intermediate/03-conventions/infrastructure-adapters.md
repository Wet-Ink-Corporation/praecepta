# Infrastructure Adapters -- Convention & Standards

**Collector ID:** 3A
**Dimension:** Convention & Standards
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. Pydantic Settings Pattern

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

All six infrastructure packages that require configuration use Pydantic `BaseSettings` with `SettingsConfigDict`. The pattern is consistently applied across the codebase with `model_config`, `Field` with descriptions, `env_prefix`, and `lru_cache` singletons for settings retrieval. Minor inconsistencies exist in `env_prefix` usage and singleton caching patterns.

**Findings:**

| File | `BaseSettings` | `SettingsConfigDict` | `env_prefix` | Singleton Cache | Notes |
|------|:-:|:-:|:-:|:-:|-------|
| `packages/infra-auth/src/praecepta/infra/auth/settings.py:25-53` | Yes | Yes | `AUTH_` | `lru_cache` at line 127 | Exemplary: `repr=False` on secrets, `ge`/`le` bounds on TTL |
| `packages/infra-persistence/src/praecepta/infra/persistence/database.py:42-63` | Yes | Yes | `DATABASE_` | No `lru_cache` | Settings instantiated inline at line 98 via `DatabaseSettings()` each time `_get_database_url()` is called; relies on module-level engine singletons for de facto caching |
| `packages/infra-persistence/src/praecepta/infra/persistence/redis_settings.py:16-49` | Yes | Yes | None (bare) | No | No `env_prefix`; fields manually prefixed with `redis_` (e.g., `redis_host`, `redis_port`). Env vars become `REDIS_HOST` etc. which works, but inconsistent with the `env_prefix` convention |
| `packages/infra-observability/src/praecepta/infra/observability/logging.py:55-76` | Yes | Yes | `""` (empty) | `lru_cache` at line 200 | Uses `alias` for env var mapping (`LOG_LEVEL`, `ENVIRONMENT`). No prefix is intentional for standard env vars |
| `packages/infra-observability/src/praecepta/infra/observability/tracing.py:42-75` | Yes | Yes | `""` (empty) | `lru_cache` at line 175 | Uses `alias` for OTEL standard env vars. Consistent with OTel conventions |
| `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/settings.py:17-66` | Yes | Yes | None (bare) | No | No `env_prefix`; relies on eventsourcing library's expected env var names (`POSTGRES_DBNAME`, etc.). No singleton cache |
| `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/settings.py:205-237` | Yes | Yes | `PROJECTION_` | No | `ProjectionPollingSettings` follows the pattern well with bounds validation |
| `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:15-23` | Yes | Yes | `CORS_` | No | `CORSSettings` is clean |
| `packages/infra-fastapi/src/praecepta/infra/fastapi/settings.py:46-55` | Yes | Yes | `APP_` | No | `AppSettings` is clean |
| `packages/infra-taskiq/src/praecepta/infra/taskiq/broker.py:48-57` | No | No | N/A | No | **Gap**: Uses bare `os.getenv("REDIS_URL")` at line 57 instead of Pydantic settings. No validation, no type safety, no .env file support |

Key issues:
- `infra-taskiq` (`broker.py:48-57`) bypasses the settings pattern entirely, using raw `os.getenv` with a hardcoded default.
- `DatabaseSettings` at `database.py:98` is re-instantiated on every call to `_get_database_url()` rather than cached via `lru_cache`.
- `RedisSettings` at `redis_settings.py:45-49` has no `env_prefix`, making it inconsistent with the convention.

---

## 2. Auth Middleware Sequencing

**Rating: 5/5 -- Optimizing**
**Severity:** Low | **Confidence:** High

The middleware sequencing is well-documented and correctly implemented via the priority-based auto-discovery system. The documented order (from `jwt_auth.py:7-8`) is:

```
Request -> RequestId -> TraceContext -> APIKey -> JWT -> RequestContext -> CORS -> Route
```

**Findings:**

| Middleware | File:Line | Priority | Band | Role |
|-----------|-----------|----------|------|------|
| `RequestIdMiddleware` | `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/request_id.py:154` | 10 | Outermost (0-99) | Generates/propagates X-Request-ID |
| `TraceContextMiddleware` | `packages/infra-observability/src/praecepta/infra/observability/middleware.py:93` | 20 | Outermost (0-99) | Binds trace_id/span_id to structlog |
| `APIKeyAuthMiddleware` | `packages/infra-auth/src/praecepta/infra/auth/middleware/api_key_auth.py:298` | 100 | Security (100-199) | API key validation, first-match-wins |
| `JWTAuthMiddleware` | `packages/infra-auth/src/praecepta/infra/auth/middleware/jwt_auth.py:348` | 150 | Security (100-199) | JWT validation, principal extraction |
| `RequestContextMiddleware` | `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/request_context.py:89` | 200 | Context (200-299) | Tenant/user context propagation |
| `TenantStateMiddleware` | `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/tenant_state.py:141` | 250 | Context (200-299) | Tenant suspension enforcement |
| `CORSMiddleware` | `packages/infra-fastapi/src/praecepta/infra/fastapi/app_factory.py:94` | N/A (first added) | Innermost | CORS headers |

The sequencing follows the correct pattern: request ID first for tracing, then auth (API key before JWT for first-match-wins), then context propagation. The app factory at `app_factory.py:116-124` sorts by priority ascending and adds in reverse (LIFO for Starlette), which correctly produces the outer-to-inner ordering. The first-match-wins pattern between API key and JWT middleware is implemented via `get_optional_principal()` checks at `api_key_auth.py:124` and `jwt_auth.py:129`.

---

## 3. JWT/JWKS Implementation

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The JWT/JWKS implementation is well-structured. `JWKSProvider` (`jwks.py:25-122`) wraps `PyJWKClient` with caching enabled and configurable TTL. Token validation in `JWTAuthMiddleware` (`jwt_auth.py:187-223`) uses RS256-only, requires `exp`, `iss`, `aud`, `sub` claims, and handles all PyJWT exception types with specific error codes.

**Findings:**

| Aspect | File:Line | Status | Notes |
|--------|-----------|--------|-------|
| `PyJWKClient` usage | `jwks.py:71-75` | Correct | `cache_jwk_set=True`, `lifespan=cache_ttl` |
| JWKS URI construction | `jwks.py:67` | Correct | `{issuer}/.well-known/jwks.json` |
| Key rotation handling | `jwks.py:70` | Correct | PyJWKClient handles kid mismatch internally |
| Algorithm restriction | `jwt_auth.py:192` | Correct | `algorithms=["RS256"]` only |
| Required claims | `jwt_auth.py:195` | Correct | `require: ["exp", "iss", "aud", "sub"]` |
| Exception handling | `jwt_auth.py:197-223` | Comprehensive | Handles 7 specific PyJWT exception types + catch-all |
| RFC 6750 compliance | `jwt_auth.py:270-273` | Correct | `WWW-Authenticate: Bearer` on all 401s |
| Principal extraction | `jwt_auth.py:296-345` | Correct | Validates `sub` as UUID, extracts `tenant_id`, `roles`, `email` |
| Cache TTL configuration | `settings.py:63-68` | Good | Bounded to 30-86400 seconds |
| Empty issuer guard | `jwks.py:60-61` | Correct | `ValueError` if issuer_url is empty |

Minor gap: The JWKS URI is constructed via simple string concatenation (`jwks.py:67`) rather than OIDC discovery (fetching `.well-known/openid-configuration` to find the `jwks_uri`). The docstring at `jwks.py:29` mentions OIDC discovery but the implementation skips it. This works for most providers but is technically not fully OIDC-compliant.

---

## 4. Dev Bypass Safety

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The development authentication bypass has multiple layers of safety. The implementation at `dev_bypass.py:23-63` is clean, well-documented, and production-hardened.

**Findings:**

| Safeguard | File:Line | Description |
|-----------|-----------|-------------|
| Production lockout | `dev_bypass.py:44-54` | `ENVIRONMENT=production` always returns `False`, regardless of `AUTH_DEV_BYPASS` value |
| Explicit opt-in | `dev_bypass.py:39-40` | Bypass only activates when `AUTH_DEV_BYPASS=true` is explicitly set |
| Header-present bypass | `jwt_auth.py:139` | Bypass only applies when `Authorization` header is absent; real tokens are always validated |
| ERROR-level logging | `dev_bypass.py:47-53` | Production bypass attempts are logged at ERROR level with structured context |
| WARNING-level logging | `dev_bypass.py:56-63` | Active bypass in non-production is logged at WARNING level |
| Synthetic claims | `__init__.py:28-36` | Uses obvious non-production values: nil UUID, `dev-tenant`, `dev-bypass@localhost` |
| Settings default | `settings.py:69-72` | `dev_bypass` defaults to `False` |
| Lazy resolution | `jwt_auth.py:109` | `resolve_dev_bypass()` is called in `__init__`, checking environment at middleware creation time |

The only observation (not a deficiency) is that the environment check uses `os.environ.get("ENVIRONMENT", "development")` rather than reading from a centralized settings object. This means the `ENVIRONMENT` variable must be set in the actual OS environment, not just in `.env` files loaded by Pydantic. This is arguably correct behavior -- production environment detection should rely on the process environment, not config files.

---

## 5. Persistence Patterns

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

The persistence package provides session factory infrastructure, RLS helpers, and tenant context propagation. However, it does not implement formal repository or unit-of-work abstractions. The package is more of a "database primitives" toolkit than a full persistence pattern implementation.

**Findings:**

| Aspect | File:Line | Status | Notes |
|--------|-----------|--------|-------|
| Session factory (async) | `database.py:102-139` | Implemented | Module-level singletons with proper pool config |
| Session factory (sync) | `database.py:171-208` | Implemented | For projections; separate pool (size=5) |
| Session dependency | `database.py:142-168` | Implemented | `DbSession` type alias via `Annotated[AsyncSession, Depends()]` |
| Engine disposal | `database.py:211-225` | Implemented | Handles both async and sync engines |
| RLS helpers | `rls_helpers.py:10-69` | Implemented | `enable_rls`, `create_tenant_isolation_policy` |
| Tenant context | `tenant_context.py:25-77` | Implemented | `SET LOCAL` via `set_config()` with parameterized values |
| Redis client | `redis_client.py:23-167` | Implemented | Factory pattern with lazy initialization |
| Repository pattern | N/A | **Missing** | No abstract `Repository` base class or protocol |
| Unit of work | N/A | **Missing** | No explicit UoW; sessions manage transactions implicitly |
| Module-level globals | `database.py:84-89` | Concern | Global mutable state for engine/session singletons |

Key gaps:
- **No Repository protocol or base class**: Domain packages directly consume SQLAlchemy `AsyncSession` via `DbSession`. This creates tight coupling between domain query logic and SQLAlchemy.
- **No Unit of Work abstraction**: Transaction management relies on implicit SQLAlchemy session behavior rather than an explicit UoW pattern.
- **Global mutable state** at `database.py:84-89`: Module-level `_engine`, `_session_factory`, `_sync_engine`, `_sync_session_factory` are mutable globals. Testing requires manual reset.
- **SQL injection risk** in `rls_helpers.py:18-20`: Table names are f-string interpolated into raw SQL (`ALTER TABLE {table_name} ...`). While these are only used in Alembic migrations (controlled context), the functions accept unvalidated string input.
- The `tenant_context.py:60` line uses `connection.execute()` with a `type: ignore[attr-defined]` comment, indicating a type system gap.

---

## 6. Observability Integration

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Structured logging via structlog and OpenTelemetry tracing are consistently configured. The observability package provides a clean lifespan hook, trace-log correlation middleware, and manual instrumentation utilities.

**Findings:**

| Aspect | File:Line | Status | Notes |
|--------|-----------|--------|-------|
| structlog configuration | `logging.py:213-263` | Comprehensive | Context merging, timestamps, sensitive data redaction, env-aware rendering |
| Sensitive data redaction | `logging.py:147-197` | Comprehensive | Checks exact match + substring match for passwords/tokens |
| JSON logs in production | `logging.py:129-135` | Correct | `environment == "production"` triggers JSON renderer |
| Console logs in dev | `logging.py:252-255` | Correct | ConsoleRenderer with colors for non-production |
| Log level validation | `logging.py:108-126` | Correct | Validates against known levels, normalizes to uppercase |
| OTel TracerProvider | `tracing.py:258-294` | Correct | Resource attributes, BatchSpanProcessor, exporter selection |
| Exporter configuration | `tracing.py:188-229` | Correct | Supports OTLP, Jaeger, Console, None; lazy imports for optional deps |
| Graceful shutdown | `tracing.py:297-314` | Correct | Idempotent `shutdown_tracing()` |
| Trace-log correlation | `middleware.py:29-96` | Correct | Binds `trace_id` and `span_id` to structlog context |
| Manual instrumentation | `instrumentation.py:97-171` | Comprehensive | `@traced_operation` decorator, `start_span` context manager |
| Lifespan hook | `__init__.py:26-41` | Correct | Priority 50 ensures early start, late shutdown |
| Health check endpoint | `_health.py:11-17` | Minimal | Stub `/healthz` only; no readiness probe, no dependency checks |

Gaps:
- **Health check is a stub** at `_health.py:11-17`: Only returns `{"status": "ok"}` with no actual dependency health checks (database, Redis, event store). The docstring at line 5 acknowledges this: "will be replaced by a full health endpoint in Step 6."
- No metrics/Prometheus integration is present (only traces and logs). This may be intentional for the pre-alpha phase.
- The `infra-auth` package uses `logging.getLogger(__name__)` (stdlib) rather than structlog's `get_logger()` throughout. While structlog still processes stdlib log records if configured, direct structlog usage would provide richer structured context.

---

## 7. TaskIQ Configuration

**Rating: 2/5 -- Initial**
**Severity:** High | **Confidence:** High

The TaskIQ configuration at `broker.py` is functional but does not follow the conventions established by other infrastructure packages. It lacks Pydantic settings, has no retry policies, no serialization configuration, and uses module-level instantiation with hardcoded defaults.

**Findings:**

| Aspect | File:Line | Status | Notes |
|--------|-----------|--------|-------|
| Broker type | `broker.py:67-69` | OK | `RedisStreamBroker` for reliable delivery with ACKs |
| Result backend | `broker.py:61-64` | OK | `RedisAsyncResultBackend` with 1hr TTL |
| Scheduler | `broker.py:75-81` | OK | Dual sources (label + Redis list) |
| Pydantic settings | N/A | **Missing** | Uses `os.getenv("REDIS_URL", "redis://localhost:6379/0")` at line 57 |
| Retry policies | N/A | **Missing** | No retry configuration, no dead-letter queue, no max_retries |
| Serialization config | N/A | **Missing** | Uses defaults (pickle); no explicit JSON serialization |
| Connection pooling | N/A | **Missing** | No pool_size, timeout, or connection management |
| Graceful shutdown | N/A | **Missing** | No shutdown hooks; broker/backend not closed on app shutdown |
| Module-level instantiation | `broker.py:61-81` | Concern | Broker, result_backend, and scheduler created at import time |
| Validation | N/A | **Missing** | No URL validation, no startup health check |

Key issues:
- **No Pydantic settings class**: Every other infra package uses `BaseSettings`. TaskIQ uses bare `os.getenv` with no validation.
- **No retry policies**: Critical for production use. Failed tasks are silently lost.
- **Module-level instantiation** (`broker.py:61-81`): Objects created at import time, before environment is fully configured. This could cause issues if the lifespan bridge has not yet populated `REDIS_URL`.
- **No lifespan integration**: No `LifespanContribution` for startup/shutdown. The broker connection is never explicitly closed.
- **Hardcoded result TTL** (`broker.py:63`): `result_ex_time=3600` is not configurable.

---

## 8. Event Sourcing Settings

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The `EventSourcingSettings` class at `settings.py:17-202` follows the Pydantic settings pattern with comprehensive configuration for PostgreSQL connection, pooling, table management, and locking. It includes a useful `to_env_dict()` method for bridging to the eventsourcing library's environment-based configuration.

**Findings:**

| Aspect | File:Line | Status | Notes |
|--------|-----------|--------|-------|
| `BaseSettings` | `settings.py:17` | Yes | Correct |
| `SettingsConfigDict` | `settings.py:62-66` | Yes | `.env` file support, `extra="ignore"` |
| Required fields | `settings.py:72-80` | Correct | `postgres_dbname`, `postgres_user`, `postgres_password` are required (`...`) |
| Secret hiding | `settings.py:78` | Correct | `repr=False` on `postgres_password` |
| Bounds validation | `settings.py:83-109` | Comprehensive | `ge`/`le` on pool_size, overflow, timeout values |
| Port validation | `settings.py:138-145` | Correct | Custom validator for 1-65535 range |
| Production warning | `settings.py:147-164` | Good | Warns if `CREATE_TABLE=true` in production |
| Env bridging | `settings.py:166-202` | Good | `to_env_dict()` converts to library-expected format |
| `ProjectionPollingSettings` | `settings.py:205-237` | Good | `PROJECTION_` prefix, bounded intervals |
| No `env_prefix` | `settings.py:62-66` | Gap | No prefix; relies on eventsourcing library's expected variable names |
| No singleton cache | N/A | Gap | No `lru_cache` wrapper; settings created fresh each time |

Minor gaps:
- No `env_prefix` on `EventSourcingSettings` -- this is arguably correct since the eventsourcing library expects specific env var names (e.g., `POSTGRES_DBNAME`), but it means the settings class cannot be namespaced alongside other services.
- No `lru_cache` singleton for `EventSourcingSettings`; the `lifespan.py:62` creates a new instance each startup, and `event_store.py:139` creates another. This is acceptable since settings are only loaded during initialization.

---

## 9. Error Handling in Adapters

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The infrastructure layer has a comprehensive error translation system. Domain exceptions are defined in the foundation layer and translated to HTTP responses by the `infra-fastapi` error handlers. Infrastructure adapters translate their specific failures into appropriate responses or domain exceptions.

**Findings:**

| Domain Exception | HTTP Status | Handler | File:Line |
|-----------------|-------------|---------|-----------|
| `AuthenticationError` | 401 | `authentication_error_handler` | `error_handlers.py:359-385` |
| `AuthorizationError` | 403 | `authorization_error_handler` | `error_handlers.py:388-410` |
| `NotFoundError` | 404 | `not_found_handler` | `error_handlers.py:223-242` |
| `ValidationError` | 422 | `validation_error_handler` | `error_handlers.py:245-267` |
| `ConflictError` | 409 | `conflict_error_handler` | `error_handlers.py:270-292` |
| `FeatureDisabledError` | 403 | `feature_disabled_handler` | `error_handlers.py:295-320` |
| `ResourceLimitExceededError` | 429 | `resource_limit_handler` | `error_handlers.py:323-356` |
| `DomainError` (base) | 400 | `domain_error_handler` | `error_handlers.py:413-438` |
| `RequestValidationError` | 422 | `request_validation_handler` | `error_handlers.py:441-477` |
| `Exception` (catch-all) | 500 | `unhandled_exception_handler` | `error_handlers.py:480-532` |

| Adapter | Exception Translation | File:Line | Notes |
|---------|----------------------|-----------|-------|
| JWT middleware | PyJWT exceptions -> JSON 401 responses | `jwt_auth.py:197-223` | 7 specific exception types handled + generic catch-all |
| API key middleware | Validation failures -> JSON 401 responses | `api_key_auth.py:134-229` | Format, lookup, revoked, hash mismatch errors |
| OIDC client | HTTP errors -> `TokenExchangeError` | `oidc_client.py:194-204` | Custom domain exception with status, error code, description |
| Tenant state middleware | Suspended tenants -> JSON 403 | `tenant_state.py:120-134` | RFC 7807 problem details |
| Event store factory | URL parse errors -> `DatabaseURLParseError` | `postgres_parser.py:35-41` | Custom exception extending `ValueError` |
| Unhandled exceptions | Sanitized 500 with correlation ID | `error_handlers.py:480-532` | Debug mode reveals type; production shows generic message |

Gap: The JWT middleware (`jwt_auth.py:197-223`) returns `JSONResponse` directly rather than raising domain exceptions. This is documented as intentional ("BaseHTTPMiddleware dispatch cannot propagate exceptions through the ASGI stack" at line 14-16), but it means the error handler registration at `error_handlers.py:569-571` for `AuthenticationError` will never be triggered by the JWT middleware path. The two error paths (middleware JSON responses vs exception handler responses) produce similar but not identical response structures.

---

## 10. Configuration Validation

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

Most infrastructure packages validate configuration at startup via Pydantic's built-in validation. Several packages include custom validators for domain-specific rules. The lifespan bridge pattern ensures the event sourcing library receives correct configuration.

**Findings:**

| Package | Validation Method | File:Line | Notes |
|---------|------------------|-----------|-------|
| infra-auth | Pydantic `Field` bounds + `validate_oauth_config()` method | `settings.py:63-68`, `93-116` | TTL bounded 30-86400; OAuth validation is opt-in (not called at startup) |
| infra-persistence (DB) | Pydantic `Field` defaults | `database.py:65-69` | No explicit validation beyond type coercion |
| infra-persistence (Redis) | Pydantic `Field` bounds + `field_validator` | `redis_settings.py:79-103` | Port validation, pool size bounded 1-100, timeout bounded >= 0.1 |
| infra-observability | Pydantic `field_validator` | `logging.py:93-126`, `tracing.py:108-141` | Log level and exporter type validated against known values |
| infra-eventsourcing | Pydantic `Field` bounds + `field_validator` | `settings.py:83-164` | Required fields, port validation, production `CREATE_TABLE` warning |
| infra-taskiq | **None** | `broker.py:48-57` | No validation; raw `os.getenv` |
| infra-fastapi | Pydantic `Field` + comma parsing | `settings.py:30-43` | Comma-separated string parsing for CORS lists |

Startup validation flow:
- `lifespan.py:43-75` (event store): Bridges settings to `os.environ` with warning logs when `PERSISTENCE_MODULE` is missing. Catches `Exception` broadly at line 63 for graceful degradation.
- `__init__.py:26-35` (observability): Calls `configure_logging()` and `configure_tracing()` at startup.
- JWT middleware: `jwks.py:60-61` raises `ValueError` if issuer URL is empty.

Gap: `AuthSettings.validate_oauth_config()` at `settings.py:93-116` is a method that must be explicitly called; it is not triggered by Pydantic's own validation pipeline. If OAuth is partially configured (e.g., `client_id` set but `client_secret` missing), no error is raised until `validate_oauth_config()` is explicitly invoked.

---

## 11. Development Constitution Compliance

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** Medium

The referenced Development Constitution document (`docs/docs/architecture/development-constitution.md`) does not exist in the repository. However, the architectural principles described in `CLAUDE.md` (4-layer hierarchy, dependency flow, PEP 420 namespaces) serve as de facto constitutional rules, enforced by `import-linter` contracts in `pyproject.toml:184-215`.

**Findings:**

| Principle | Status | Evidence |
|-----------|--------|----------|
| 4-layer dependency hierarchy | Enforced | `pyproject.toml:206-215`: `import-linter` layers contract: integration > domain > infra > foundation |
| Foundation purity | Enforced | `pyproject.toml:189-204`: Forbidden modules contract blocks fastapi, sqlalchemy, httpx, structlog, opentelemetry, taskiq, redis from foundation |
| PEP 420 namespace packages | Followed | All intermediate directories lack `__init__.py`; leaf packages have `__init__.py` + `py.typed` |
| `env_prefix` convention | Mostly followed | 5 of 6 settings classes use appropriate prefixes; TaskIQ is the exception |
| Entry-point auto-discovery | Followed | All middleware, lifespans, and routers use `MiddlewareContribution`, `LifespanContribution`, registered via entry points |
| `extra="ignore"` on settings | Consistently applied | All 8 `SettingsConfigDict` instances use `extra="ignore"` |

Gaps:
- The Development Constitution document referenced in the checklist does not exist in the repo. Without this document, compliance assessment relies on the architectural rules inferred from `CLAUDE.md` and tooling configuration.
- The accepted exception for domain packages depending on `infra-eventsourcing` (documented in `CLAUDE.md`) is architecturally sound but not formally captured in a PADR since no PADRs exist in the repository.
- None of the PADRs referenced in the checklist (PADR-103, PADR-106, PADR-110, PADR-116, PADR-120) exist in the repository. This means the decision rationale for infrastructure patterns is not formally documented.

---

## 12. Dependency Injection Patterns

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The codebase uses a mix of DI patterns: FastAPI's `Depends()` for request-scoped injection, constructor injection for middleware, Protocol-based interfaces for cross-layer contracts, and the entry-point auto-discovery system for plugin-style composition.

**Findings:**

| Pattern | File:Line | Description |
|---------|-----------|-------------|
| FastAPI `Depends` | `dependencies.py:38-54` | `get_current_principal()` and `CurrentPrincipal` type alias |
| FastAPI `Depends` | `database.py:142-168` | `get_db_session()` async generator and `DbSession` type alias |
| Constructor injection | `jwt_auth.py:83-112` | `JWTAuthMiddleware.__init__` accepts `jwks_provider`, `issuer`, `audience` |
| Constructor injection | `api_key_auth.py:78-102` | `APIKeyAuthMiddleware.__init__` accepts `key_prefix`, `excluded_prefixes` |
| Constructor injection | `tenant_state.py:71-81` | `TenantStateMiddleware.__init__` accepts `tenant_status_checker` callable |
| Protocol interface | `ports/api_key_generator.py:20-75` | `APIKeyGeneratorPort` protocol in foundation layer |
| Protocol implementation | `api_key_generator.py:26-131` | `APIKeyGenerator` in infra-auth implements the port |
| App state injection | `api_key_auth.py:156` | `request.app.state.agent_api_key_repo` -- runtime lazy access |
| Entry-point discovery | `app_factory.py:70-78` | Lifespan hooks discovered from `praecepta.lifespan` group |
| Entry-point discovery | `app_factory.py:105-114` | Middleware discovered from `praecepta.middleware` group |
| `lru_cache` singletons | `settings.py:127`, `logging.py:200`, `tracing.py:175` | Cached settings instances |
| Factory pattern | `event_store.py:57-218` | `EventStoreFactory` with `from_env()`, `from_database_url()` class methods |
| Factory pattern | `redis_client.py:23-167` | `RedisFactory` with `from_env()`, `from_url()` class methods |

Strengths:
- The `APIKeyGeneratorPort` protocol at `ports/api_key_generator.py:20` with `@runtime_checkable` enables proper DI and testability.
- Constructor injection on middleware classes allows full testability without app state.
- The `MiddlewareContribution` / `LifespanContribution` / `ErrorHandlerContribution` system provides clean plugin-style composition.

Gaps:
- `api_key_auth.py:156` accesses `request.app.state.agent_api_key_repo` at runtime rather than receiving the repository via constructor injection. The docstring at line 93-95 explains this is for lifecycle ordering, but it creates a hidden runtime dependency.
- Module-level mutable globals in `database.py:84-89` (`_engine`, `_session_factory`, etc.) are a DI anti-pattern. A proper factory or provider pattern would be more testable.
- The `infra-taskiq` broker at `broker.py:61-81` uses module-level instantiation with no DI seam -- the broker is a module-level singleton with no way to swap implementations or configure via DI.

---

## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | Pydantic Settings Pattern | 4/5 | Medium |
| 2 | Auth Middleware Sequencing | 5/5 | Low |
| 3 | JWT/JWKS Implementation | 4/5 | Low |
| 4 | Dev Bypass Safety | 5/5 | Info |
| 5 | Persistence Patterns | 3/5 | Medium |
| 6 | Observability Integration | 4/5 | Low |
| 7 | TaskIQ Configuration | 2/5 | High |
| 8 | Event Sourcing Settings | 4/5 | Low |
| 9 | Error Handling in Adapters | 4/5 | Low |
| 10 | Configuration Validation | 4/5 | Medium |
| 11 | Development Constitution Compliance | 3/5 | Medium |
| 12 | Dependency Injection Patterns | 4/5 | Low |

**Overall average: 3.8/5**

**Top risks:**
1. **TaskIQ (item 7, 2/5, High)**: The only infra package that bypasses Pydantic settings entirely. No retry policies, no serialization config, module-level instantiation, and no lifespan integration.
2. **Persistence patterns (item 5, 3/5, Medium)**: No repository or unit-of-work abstractions. Direct SQLAlchemy session exposure to domain consumers creates coupling.
3. **Missing PADRs (item 11, 3/5, Medium)**: None of the referenced architectural decision records exist in the repository. The Development Constitution document is also absent. Architectural decisions are implicit in code rather than formally documented.
