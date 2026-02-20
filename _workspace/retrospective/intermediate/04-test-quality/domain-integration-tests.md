# Test Quality Audit: Domain, Auth, FastAPI & Integration Tests

**Collector ID:** 4B
**Dimension:** Test Quality
**Date:** 2026-02-18
**Scope:** Domain packages (tenancy, identity), auth middleware, FastAPI integration, eventsourcing infrastructure, and root-level integration tests

---

## 1. Domain Aggregate Event Tests

**Maturity: 5 / 5 (Optimizing)**

The tenant and identity aggregates have thorough event-emission tests covering every state transition, including happy paths, idempotent operations, invalid transitions, and audit metadata on events.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| Tenant creation emits `Provisioned` event, validated by class name | `packages/domain-tenancy/tests/test_tenant.py:93-97` | Info | High |
| Every transition (activate, suspend, reactivate, decommission) tests both state change AND event emission | `packages/domain-tenancy/tests/test_tenant.py:139-145`, `217-223`, `289-295`, `361-367` | Info | High |
| Audit metadata (initiated_by, correlation_id) verified on every transition event | `packages/domain-tenancy/tests/test_tenant.py:147-154`, `225-238`, `297-304`, `369-380` | Info | High |
| Config update and metadata update event emission tested | `packages/domain-tenancy/tests/test_tenant.py:392-402`, `514-523` | Info | High |
| DataDeleted audit events tested for decommissioned tenants | `packages/domain-tenancy/tests/test_tenant.py:577-611` | Info | High |
| Full lifecycle test validates version counter across 5 transitions | `packages/domain-tenancy/tests/test_tenant.py:557-564` | Info | High |
| User aggregate `Provisioned` event carries all OIDC claims | `packages/domain-identity/tests/test_user.py:40-49` | Info | High |
| Agent `Registered` event emitted with all creation fields | `packages/domain-identity/tests/test_agent.py:16-27` | Info | High |
| Agent API key lifecycle (issue, rotate) emits correct events | `packages/domain-identity/tests/test_agent.py:145-204` | Info | High |
| User `ProfileUpdated` and `PreferencesUpdated` events verified | `packages/domain-identity/tests/test_user.py:102-144` | Info | High |
| Idempotent operations (e.g., suspend when already suspended) produce zero events | `packages/domain-tenancy/tests/test_tenant.py:200-204`, `packages/domain-identity/tests/test_agent.py:87-98` | Info | High |
| Event class names asserted via string comparison (`__class__.__name__`) rather than importing domain event types directly | `packages/domain-tenancy/tests/test_tenant.py:97`, `packages/domain-identity/tests/test_user.py:45` | Low | High |

**Assessment:** Exemplary. Every aggregate operation is tested for correct event emission, event payload content, audit metadata propagation, and version incrementing. Invalid state transitions are tested from all inapplicable source states.

---

## 2. Projection Tests

**Maturity: 5 / 5 (Optimizing)**

Projections are tested with mock repositories. Tests verify topic subscriptions, policy dispatch for each event type, and correct repository calls.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| TenantListProjection subscribes to all 5 lifecycle events | `packages/domain-tenancy/tests/test_tenant_list_projection.py:41-62` | Info | High |
| Each lifecycle event dispatches correct repository call (upsert vs update_status) | `packages/domain-tenancy/tests/test_tenant_list_projection.py:69-149` | Info | High |
| TenantListProjection ignores non-lifecycle events (ConfigUpdated) | `packages/domain-tenancy/tests/test_tenant_list_projection.py:141-149` | Info | High |
| TenantConfigProjection tests upsert + cache invalidation on ConfigUpdated | `packages/domain-tenancy/tests/test_tenant_config_projection.py:45-58` | Info | High |
| TenantConfigProjection handles None cache gracefully | `packages/domain-tenancy/tests/test_tenant_config_projection.py:72-79` | Info | High |
| TenantConfigProjection ignores non-config events | `packages/domain-tenancy/tests/test_tenant_config_projection.py:81-88` | Info | High |
| UserProfileProjection tests Provisioned, ProfileUpdated, PreferencesUpdated, and unknown events | `packages/domain-identity/tests/test_user_profile_projection.py:65-113` | Info | High |
| UserProfileProjection display_name fallback logic tested (name -> email prefix -> "User") | `packages/domain-identity/tests/test_user_profile_projection.py:75-89` | Info | High |
| AgentAPIKeyProjection tests issuance upsert and rotation (revoke+upsert) | `packages/domain-identity/tests/test_agent_api_key_projection.py:58-88` | Info | High |
| AgentAPIKeyProjection ignores unrelated events | `packages/domain-identity/tests/test_agent_api_key_projection.py:81-88` | Info | High |
| Projections do not test multi-event sequences replayed in order to produce a final read model state | `packages/domain-tenancy/tests/test_tenant_list_projection.py` (entire file) | Medium | High |

**Assessment:** Strong mock-based unit testing of projection policy methods. Each event type triggers the correct repository mutation. One gap: no projection tests replay a sequence of events to verify cumulative read model state -- each test dispatches a single event in isolation.

---

## 3. Auth Middleware Tests

**Maturity: 5 / 5 (Optimizing)**

JWT and API key middleware are tested with real Starlette/ASGI test clients, covering excluded paths, missing tokens, invalid formats, valid flows, revoked keys, wrong secrets, and dev bypass.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| JWT: excluded path /health skips auth | `packages/infra-auth/tests/test_jwt_auth_middleware.py:58-63` | Info | High |
| JWT: missing Authorization returns 401 with MISSING_TOKEN error code | `packages/infra-auth/tests/test_jwt_auth_middleware.py:70-77` | Info | High |
| JWT: non-Bearer scheme returns 401 with INVALID_FORMAT | `packages/infra-auth/tests/test_jwt_auth_middleware.py:79-85` | Info | High |
| JWT: empty bearer token returns 401 | `packages/infra-auth/tests/test_jwt_auth_middleware.py:87-91` | Info | High |
| JWT: no JWKS provider returns 503 SERVICE_UNAVAILABLE | `packages/infra-auth/tests/test_jwt_auth_middleware.py:93-99` | Info | High |
| JWT: valid token passes through to handler | `packages/infra-auth/tests/test_jwt_auth_middleware.py:106-130` | Info | High |
| JWT: dev bypass injects synthetic claims | `packages/infra-auth/tests/test_jwt_auth_middleware.py:137-143` | Info | High |
| API key: missing key passes through (layered auth) | `packages/infra-auth/tests/test_api_key_auth_middleware.py:69-75` | Info | High |
| API key: wrong prefix returns 401 INVALID_FORMAT | `packages/infra-auth/tests/test_api_key_auth_middleware.py:89-94` | Info | High |
| API key: too-short key returns 401 INVALID_FORMAT | `packages/infra-auth/tests/test_api_key_auth_middleware.py:96-101` | Info | High |
| API key: unknown key_id returns 401 INVALID_KEY | `packages/infra-auth/tests/test_api_key_auth_middleware.py:103-108` | Info | High |
| API key: valid key with real hash verification passes | `packages/infra-auth/tests/test_api_key_auth_middleware.py:115-136` | Info | High |
| API key: revoked key returns 401 REVOKED_KEY | `packages/infra-auth/tests/test_api_key_auth_middleware.py:138-159` | Info | High |
| API key: wrong secret returns 401 INVALID_KEY | `packages/infra-auth/tests/test_api_key_auth_middleware.py:161-184` | Info | High |
| Dev bypass: production blocks bypass, development/staging allows it | `packages/infra-auth/tests/test_dev_bypass.py:14-31` | Info | High |
| AuthSettings: defaults, env prefix loading, OAuth config validation all tested | `packages/infra-auth/tests/test_settings.py:14-86` | Info | High |
| JWT expired token scenario not explicitly tested (relies on mocked decode) | `packages/infra-auth/tests/test_jwt_auth_middleware.py` (entire file) | Low | Medium |
| No test verifies WWW-Authenticate header content on valid JWT flow | `packages/infra-auth/tests/test_jwt_auth_middleware.py:106-130` | Low | Medium |

**Assessment:** Comprehensive coverage of authentication edge cases. Both middleware types tested with real ASGI test clients. Error codes and HTTP status codes are verified. The API key tests use real cryptographic hashing via APIKeyGenerator, which is excellent.

---

## 4. FastAPI Integration Tests

**Maturity: 5 / 5 (Optimizing)**

App factory tests are well-isolated, suppress entry-point discovery to avoid external dependencies, and cover router mounting, error handler registration, lifespan hooks (including ordering), and entry-point auto-discovery.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| create_app returns FastAPI instance and applies settings | `packages/infra-fastapi/tests/test_app_factory.py:36-52` | Info | High |
| Extra routers are mounted and reachable | `packages/infra-fastapi/tests/test_app_factory.py:57-72` | Info | High |
| Extra error handlers registered and invoked correctly | `packages/infra-fastapi/tests/test_app_factory.py:77-104` | Info | High |
| Lifespan hooks execute in priority order | `packages/infra-fastapi/tests/test_app_factory.py:126-148` | Info | High |
| Auto-discovery finds _health_stub router | `packages/infra-fastapi/tests/test_discovery_integration.py:14-27` | Info | High |
| Exclude by group hides discovered routers | `packages/infra-fastapi/tests/test_discovery_integration.py:30-38` | Info | High |
| Exclude by name hides specific entry point | `packages/infra-fastapi/tests/test_discovery_integration.py:41-49` | Info | High |
| Error handlers tested for all domain exceptions (NotFound, Validation, Conflict, FeatureDisabled, ResourceLimit, Authentication, Authorization, DomainError fallback, RequestValidation, Unhandled) | `packages/infra-fastapi/tests/test_error_handlers.py:168-386` | Info | High |
| Sanitization logic for sensitive keys, connection strings, UUIDs, datetimes, nested dicts thoroughly tested | `packages/infra-fastapi/tests/test_error_handlers.py:92-161` | Info | High |
| ProblemDetail model serialization tested including exclude_none | `packages/infra-fastapi/tests/test_error_handlers.py:46-84` | Info | High |
| Unhandled exception returns 500 with correlation_id, different behavior in debug mode | `packages/infra-fastapi/tests/test_error_handlers.py:354-386` | Info | High |
| Content-type verified as application/problem+json | `packages/infra-fastapi/tests/test_error_handlers.py:187-196` | Info | High |
| Discovery integration tests marked `@pytest.mark.unit` but exercise real entry-point discovery (semi-integration behavior) | `packages/infra-fastapi/tests/test_discovery_integration.py:13-14` | Low | High |

**Assessment:** Exemplary. The app factory is tested in isolation with comprehensive error handler coverage. The discovery integration tests validate real entry-point wiring. All RFC 7807 fields and content types are verified.

---

## 5. Root Integration Tests

**Maturity: 4 / 5 (Managed)**

Root-level integration tests use a Dog School example app to verify the full stack: auto-discovery, middleware, error handling, and API lifecycles.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| Auto-discovery verified: health endpoint, router mounting, error handlers, CORS | `tests/test_integration_app_factory.py:12-41` | Info | High |
| Dog School domain aggregate tested independently (no HTTP) | `tests/test_integration_dog_school.py:12-34` | Info | High |
| Full API lifecycle: register, retrieve, learn tricks workflow | `tests/test_integration_dog_school.py:41-64` | Info | High |
| Tenant ID flows from X-Tenant-ID header into aggregate | `tests/test_integration_dog_school.py:66-69` | Info | High |
| RFC 7807 error responses verified for 404, 422 (domain), 422 (request validation) | `tests/test_integration_error_handling.py:9-74` | Info | High |
| Middleware stack: RequestIdMiddleware generates/propagates X-Request-ID (validated as UUID) | `tests/test_integration_middleware.py:14-22` | Info | High |
| Middleware stack: RequestContextMiddleware generates/propagates X-Correlation-ID | `tests/test_integration_middleware.py:30-39` | Info | High |
| Tenant context propagation verified in handler | `tests/test_integration_middleware.py:46-50` | Info | High |
| Smoke tests verify all 11 packages are importable via PEP 420 namespace | `tests/test_smoke.py:10-51` | Info | High |
| Shared conftest provides dog_school_app, client, and tenant_headers fixtures | `tests/conftest.py:27-48` | Info | High |
| Auth middleware excluded in integration tests (no JWT/API key verification in stack) | `tests/conftest.py:16-23` | Medium | High |
| No integration test exercises the full auth middleware stack with the Dog School app | `tests/conftest.py:16-23` | Medium | High |
| Integration tests do not test concurrent/parallel request handling | All integration test files | Low | High |
| No integration test for the eventsourcing persistence round-trip (event store excluded) | `tests/conftest.py:19` | Medium | High |

**Assessment:** Good integration coverage of the HTTP stack, middleware, and error handling. The Dog School example provides a clean vertical slice. Gaps exist in auth stack integration and event store persistence round-trips, both of which are excluded from integration fixtures.

---

## 6. Fixtures Reuse

**Maturity: 4 / 5 (Managed)**

Each domain package has a conftest.py with shared fixtures. Root-level integration tests share a conftest. However, some test files re-create fixtures inline instead of using the shared ones.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| Tenancy conftest provides new_tenant, active_tenant, suspended_tenant, decommissioned_tenant | `packages/domain-tenancy/tests/conftest.py:10-45` | Info | High |
| Identity conftest provides user and agent fixtures | `packages/domain-identity/tests/conftest.py:11-29` | Info | High |
| Root conftest provides dog_school_app, client, tenant_headers | `tests/conftest.py:27-48` | Info | High |
| test_tenant.py uses inline `_new_tenant()` helper instead of conftest fixtures | `packages/domain-tenancy/tests/test_tenant.py:20-28` | Low | High |
| test_user.py uses inline `_new_user()` helper instead of conftest user fixture | `packages/domain-identity/tests/test_user.py:12-20` | Low | High |
| test_agent.py creates Agent instances inline in every test method, not using conftest agent fixture | `packages/domain-identity/tests/test_agent.py:17-21`, `29-34` (repeated ~15 times) | Medium | High |
| Projection tests create mock events via inline helpers -- these could be shared across projection test files | `packages/domain-tenancy/tests/test_tenant_list_projection.py:16-34`, `packages/domain-tenancy/tests/test_tenant_config_projection.py:14-29` | Low | High |
| Conftest fixtures for tenancy are not used by any test file (all use inline helpers or class methods) | `packages/domain-tenancy/tests/conftest.py` (entire file) | Medium | High |
| Conftest fixtures for identity not used by test_user.py or test_agent.py | `packages/domain-identity/tests/conftest.py` (entire file) | Medium | High |

**Assessment:** Fixtures are defined but underutilized. All aggregate test files prefer inline helper functions (`_new_tenant()`, `_new_user()`) or class-level `_make_*()` methods. This is defensible for fine-grained control but means the conftest fixtures are effectively dead code.

---

## 7. Test Data Factories

**Maturity: 3 / 5 (Defined)**

Test data creation uses inline helper functions and class methods. There are no formal factory libraries (factory_boy, etc.), but the helpers are consistent within each file.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| `_new_tenant()` factory with keyword defaults | `packages/domain-tenancy/tests/test_tenant.py:20-28` | Info | High |
| `_new_user()` factory with keyword defaults | `packages/domain-identity/tests/test_user.py:12-20` | Info | High |
| `_make_event()` factory for mock lifecycle events | `packages/domain-tenancy/tests/test_tenant_list_projection.py:16-34` | Info | High |
| `_make_config_updated_event()` factory for mock config events | `packages/domain-tenancy/tests/test_tenant_config_projection.py:14-29` | Info | High |
| `_make_provisioned_event()`, `_make_profile_updated_event()`, `_make_preferences_updated_event()` | `packages/domain-identity/tests/test_user_profile_projection.py:15-51` | Info | High |
| `_make_api_key_issued_event()`, `_make_api_key_rotated_event()` | `packages/domain-identity/tests/test_agent_api_key_projection.py:15-47` | Info | High |
| `_make_mock_app()` helper duplicated between slug_registry and oidc_sub_registry tests | `packages/domain-tenancy/tests/test_slug_registry.py:14-24`, `packages/domain-identity/tests/test_oidc_sub_registry.py:14-25` | Medium | High |
| `_mock_session_factory()` helper in tenant_repository | `packages/domain-tenancy/tests/test_tenant_repository.py:12-23` | Info | High |
| `_make_session_factory()` helper in config_repository (slightly different pattern from tenant_repository) | `packages/domain-tenancy/tests/test_config_repository.py:14-30` | Low | High |
| No use of factory_boy, Faker, or similar structured factory libraries | All test files | Low | Medium |
| Each class that needs state progression has `_make_active_tenant()`, `_make_suspended_tenant()` etc. as methods | `packages/domain-tenancy/tests/test_tenant.py:166-169`, `245-253`, `311-313`, `387-389`, `500-502`, `571-575` | Info | High |
| FakeKeyRepo and FakeKeyRecord provide structured test doubles for API key auth tests | `packages/infra-auth/tests/test_api_key_auth_middleware.py:23-39` | Info | High |

**Assessment:** Consistent use of helper functions and class methods per file. The pattern is well-established but not centralized. Similar mock-app factories are duplicated across packages rather than shared. No formal factory library is used.

---

## 8. Async Integration

**Maturity: 3 / 5 (Defined)**

Most tests are synchronous. The framework uses ASGI (Starlette/FastAPI) but tests interact via synchronous TestClient. Async lifespan hooks are tested indirectly.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| FastAPI error handler tests use sync TestClient wrapping async handlers | `packages/infra-fastapi/tests/test_error_handlers.py:168-386` | Info | High |
| JWT auth middleware async dispatch tested via sync TestClient | `packages/infra-auth/tests/test_jwt_auth_middleware.py:58-143` | Info | High |
| API key auth middleware async dispatch tested via sync TestClient | `packages/infra-auth/tests/test_api_key_auth_middleware.py:65-184` | Info | High |
| Lifespan hooks (async context managers) executed via TestClient context manager | `packages/infra-fastapi/tests/test_app_factory.py:109-148` | Info | High |
| ProjectionPoller tests poll loop synchronously (direct _poll_loop() call) | `packages/infra-eventsourcing/tests/test_projection_poller.py:208-280` | Info | High |
| No `pytest.mark.anyio` or `@pytest.mark.asyncio` tests in any of the examined files | All examined test files | Medium | High |
| No direct async/await testing of middleware dispatch methods | `packages/infra-auth/tests/test_jwt_auth_middleware.py` (entire file) | Low | Medium |
| Integration tests use sync TestClient exclusively | `tests/conftest.py:35-38` | Info | High |

**Assessment:** All async code is tested indirectly through synchronous TestClient. This is standard practice for FastAPI/Starlette and provides valid coverage. However, there are no `async def test_*` tests exercising async code paths directly, which limits ability to test async-specific behaviors (e.g., concurrent request handling, async context variable propagation).

---

## 9. Error Scenario Coverage

**Maturity: 5 / 5 (Optimizing)**

Error scenarios are thoroughly covered across all layers: aggregate validation, state machine violations, auth failures, API error responses, and edge cases.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| Invalid slug format rejected | `packages/domain-tenancy/tests/test_tenant.py:75-77` | Info | High |
| Empty name rejected | `packages/domain-tenancy/tests/test_tenant.py:79-81` | Info | High |
| Mismatched tenant_id/slug rejected | `packages/domain-tenancy/tests/test_tenant.py:83-91` | Info | High |
| Invalid state transitions tested from every inapplicable state (6 tests for decommission blocking) | `packages/domain-tenancy/tests/test_tenant.py:125-137`, `206-215`, `278-287`, `338-358` | Info | High |
| Config update on non-ACTIVE state raises InvalidStateTransitionError | `packages/domain-tenancy/tests/test_tenant.py:404-421` | Info | High |
| DataDeleted on non-DECOMMISSIONED state raises error | `packages/domain-tenancy/tests/test_tenant.py:590-596` | Info | High |
| Empty OIDC sub rejected | `packages/domain-identity/tests/test_user.py:76-78` | Info | High |
| Oversized OIDC sub rejected | `packages/domain-identity/tests/test_user.py:80-83` | Info | High |
| Invalid agent type ID format rejected | `packages/domain-identity/tests/test_agent.py:45-51` | Info | High |
| Empty display name rejected | `packages/domain-identity/tests/test_agent.py:53-59` | Info | High |
| API key issuance on suspended agent raises ValidationError | `packages/domain-identity/tests/test_agent.py:165-177` | Info | High |
| API key rotation without active key raises ValidationError | `packages/domain-identity/tests/test_agent.py:206-216` | Info | High |
| API key rotation on suspended agent raises ValidationError | `packages/domain-identity/tests/test_agent.py:218-234` | Info | High |
| Slug conflict (UniqueViolation) raises ConflictError | `packages/domain-tenancy/tests/test_slug_registry.py:39-54` | Info | High |
| Cross-tenant user provisioning raises ConflictError | `packages/domain-identity/tests/test_user_provisioning.py:42-52` | Info | High |
| Save failure releases OIDC reservation | `packages/domain-identity/tests/test_user_provisioning.py:76-85` | Info | High |
| Race condition retry on reserve conflict | `packages/domain-identity/tests/test_user_provisioning.py:92-106` | Info | High |
| JWT: missing token, invalid format, empty bearer, no JWKS | `packages/infra-auth/tests/test_jwt_auth_middleware.py:70-99` | Info | High |
| API key: wrong prefix, too short, unknown key_id, revoked key, wrong secret | `packages/infra-auth/tests/test_api_key_auth_middleware.py:89-184` | Info | High |
| All domain exceptions mapped to HTTP status codes with correct error_code | `packages/infra-fastapi/tests/test_error_handlers.py:168-386` | Info | High |
| Invalid timestamp column injection rejected in TenantRepository | `packages/domain-tenancy/tests/test_tenant_repository.py:121-131` | Info | High |
| OAuth config validation errors (missing client_id, missing secret, invalid redirect URI) | `packages/infra-auth/tests/test_settings.py:50-79` | Info | High |
| Unhandled exception returns sanitized 500 in production, detailed in debug | `packages/infra-fastapi/tests/test_error_handlers.py:354-386` | Info | High |
| Password/connection-string redaction in error context | `packages/infra-fastapi/tests/test_error_handlers.py:125-135` | Info | High |

**Assessment:** Exemplary error coverage. Every validation rule, state transition guard, authentication failure mode, and error response format is tested. The sanitization of sensitive data in error responses is particularly well-covered.

---

## 10. Event Sourcing Tests

**Maturity: 4 / 5 (Managed)**

EventStoreFactory, ProjectionRunner (deprecated), ProjectionPoller, and ProjectionRebuilder are all tested. The poller tests are notably thorough.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| EventStoreFactory construction, settings, and URL parsing tested | `packages/infra-eventsourcing/tests/test_event_store.py:14-98` | Info | High |
| from_database_url parses all components correctly (host, port, dbname, user, password) | `packages/infra-eventsourcing/tests/test_event_store.py:36-53` | Info | High |
| from_env tested with DATABASE_URL and individual POSTGRES_* vars | `packages/infra-eventsourcing/tests/test_event_store.py:101-137` | Info | High |
| get_event_store singleton caching verified (same instance returned) | `packages/infra-eventsourcing/tests/test_event_store.py:160-173` | Info | High |
| Close behavior tested (no-op when not initialized, delegates when initialized) | `packages/infra-eventsourcing/tests/test_event_store.py:55-71` | Info | High |
| Recorder lazy initialization + reuse verified | `packages/infra-eventsourcing/tests/test_event_store.py:73-98` | Info | High |
| BaseProjection contract: abstract methods verified | `packages/infra-eventsourcing/tests/test_projection_base.py:14-28` | Info | High |
| ProjectionRunner deprecation warning emitted | `packages/infra-eventsourcing/tests/test_projection_base.py:43-48` | Info | High |
| ProjectionPoller lifecycle: not running initially, get raises when not started, stop when not started safe, start twice raises | `packages/infra-eventsourcing/tests/test_projection_poller.py:74-109` | Info | High |
| ProjectionPoller start/stop creates thread, sets running, stops cleanly | `packages/infra-eventsourcing/tests/test_projection_poller.py:119-198` | Info | High |
| ProjectionPoller context manager (with statement) starts and stops | `packages/infra-eventsourcing/tests/test_projection_poller.py:174-198` | Info | High |
| Poll loop calls pull_and_process on each projection | `packages/infra-eventsourcing/tests/test_projection_poller.py:208-243` | Info | High |
| Poll loop catches exceptions without crashing | `packages/infra-eventsourcing/tests/test_projection_poller.py:245-280` | Info | High |
| Poll loop respects stop event between projections | `packages/infra-eventsourcing/tests/test_projection_poller.py:282-317` | Info | High |
| Multiple projections all processed in each cycle | `packages/infra-eventsourcing/tests/test_projection_poller.py:341-385` | Info | High |
| ProjectionRebuilder calls clear_read_model and resets tracking position | `packages/infra-eventsourcing/tests/test_projection_base.py:116-136` | Info | High |
| Rebuilder handles missing delete_tracking_record gracefully | `packages/infra-eventsourcing/tests/test_projection_base.py:138-149` | Info | High |
| ProjectionPollingSettings boundary validation tested (interval, timeout) | `packages/infra-eventsourcing/tests/test_projection_poller.py:40-65` | Info | High |
| No test with a real PostgreSQL event store (all mocked) | `packages/infra-eventsourcing/tests/` (all files) | Medium | High |
| TenantApplication and UserApplication round-trip save/retrieve tested with in-memory store | `packages/domain-tenancy/tests/test_tenant_app.py:22-46`, `packages/domain-identity/tests/test_user_app.py:22-34` | Info | High |

**Assessment:** Strong coverage of the eventsourcing infrastructure layer. The ProjectionPoller is particularly well-tested with deterministic poll-loop testing. No real database integration tests exist (all mocked), which is appropriate for unit tests but means the PostgreSQL adapter is untested.

---

## 11. Marker Consistency

**Maturity: 4 / 5 (Managed)**

Tests consistently use `@pytest.mark.unit` or `@pytest.mark.integration`. A few inconsistencies exist.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| All tenancy aggregate tests marked `@pytest.mark.unit` at class level | `packages/domain-tenancy/tests/test_tenant.py:31`, `108`, `162`, `241`, `307`, `383`, `496`, `553`, `567` | Info | High |
| All identity aggregate tests marked `@pytest.mark.unit` at class level | `packages/domain-identity/tests/test_user.py:23`, `98`, `packages/domain-identity/tests/test_agent.py:12`, `69`, `110`, `141` | Info | High |
| All auth tests marked `@pytest.mark.unit` at class level | `packages/infra-auth/tests/test_jwt_auth_middleware.py:54`, `66`, `102`, `133` | Info | High |
| All eventsourcing tests marked `@pytest.mark.unit` at class level | `packages/infra-eventsourcing/tests/test_event_store.py:13`, `101`, `140` | Info | High |
| Root integration tests all marked `@pytest.mark.integration` | `tests/test_integration_app_factory.py:8`, `tests/test_integration_dog_school.py:12`, `37` | Info | High |
| Smoke tests (`test_smoke.py`) have NO pytest markers | `tests/test_smoke.py:10-51` | Medium | High |
| FastAPI app_factory tests apply markers at method level, not class level | `packages/infra-fastapi/tests/test_app_factory.py:35`, `49`, `56`, `77`, `109`, `125` | Low | High |
| Discovery integration tests marked `unit` despite exercising real entry-point discovery | `packages/infra-fastapi/tests/test_discovery_integration.py:13`, `20`, `29`, `41` | Medium | High |
| Error handler test classes apply markers at method level rather than class level | `packages/infra-fastapi/tests/test_error_handlers.py:46`, `59`, `72`, `93`, etc. | Low | High |

**Assessment:** Overall consistent. The two notable issues are: smoke tests lacking markers (should likely be `unit` or their own marker), and discovery integration tests being marked `unit` when they rely on installed entry points (semi-integration behavior).

---

## 12. Test Documentation

**Maturity: 4 / 5 (Managed)**

Test classes have docstrings explaining the test category. Test method names are descriptive. Module-level docstrings explain purpose. Some complex setup lacks inline comments.

### Findings

| Finding | File:Line | Severity | Confidence |
|---------|-----------|----------|------------|
| Module-level docstring explains eventsourcing library __init__ quirk | `packages/domain-tenancy/tests/test_tenant.py:1-7` | Info | High |
| Test classes have concise docstrings (e.g., "PROVISIONING -> ACTIVE transition") | `packages/domain-tenancy/tests/test_tenant.py:109`, `163`, `242`, `308` | Info | High |
| Smoke test module docstring explains PEP 420 namespace verification | `tests/test_smoke.py:1-5` | Info | High |
| ProjectionRunner deprecation noted in class docstring | `packages/infra-eventsourcing/tests/test_projection_base.py:33` | Info | High |
| Complex mock event factory explains each field | `packages/domain-tenancy/tests/test_tenant_list_projection.py:16-34` | Info | High |
| Test names are consistently descriptive: `test_raises_conflict_on_unique_violation`, `test_releases_reservation_on_save_failure` | Multiple files | Info | High |
| Generic test for config keys has explanatory docstring | `packages/domain-tenancy/tests/test_tenant.py:451` | Info | High |
| Race condition test class documents the scenario | `packages/domain-identity/tests/test_user_provisioning.py:88-90` | Info | High |
| Poll loop tests have inline comments explaining the counted_wait mechanism | `packages/infra-eventsourcing/tests/test_projection_poller.py:227-239` | Info | High |
| Some projection test methods lack docstrings (simple enough to not need them) | `packages/domain-tenancy/tests/test_tenant_config_projection.py:45`, `60`, `72` | Info | High |
| OidcSubRegistry test classes lack docstrings (class name alone is sufficient) | `packages/domain-identity/tests/test_oidc_sub_registry.py:28`, `39`, `51`, `61`, `77` | Low | High |

**Assessment:** Good documentation practices. Module and class docstrings establish context. Test names are consistently descriptive enough to understand intent. Complex setups include comments. The only gap is that some simpler test classes omit docstrings, though their names are self-explanatory.

---

## Summary Statistics

| # | Checklist Item | Maturity | Key Gap |
|---|----------------|----------|---------|
| 1 | Domain Aggregate Event Tests | 5 | Event types asserted by string name, not imported type |
| 2 | Projection Tests | 5 | No multi-event sequence replay tests |
| 3 | Auth Middleware Tests | 5 | No explicit expired-token test (relies on mock) |
| 4 | FastAPI Integration Tests | 5 | Discovery tests marked `unit` despite real discovery |
| 5 | Root Integration Tests | 4 | Auth stack and event store excluded from integration fixture |
| 6 | Fixtures Reuse | 4 | Conftest fixtures defined but unused (dead code) |
| 7 | Test Data Factories | 3 | No centralized factory library; mock-app helpers duplicated |
| 8 | Async Integration | 3 | No direct async test functions; all async tested via sync client |
| 9 | Error Scenario Coverage | 5 | None -- comprehensive |
| 10 | Event Sourcing Tests | 4 | No real database integration tests |
| 11 | Marker Consistency | 4 | Smoke tests unmarkered; discovery tests mislabeled |
| 12 | Test Documentation | 4 | Minor gaps in simple test class docstrings |

**Overall Average Maturity: 4.25 / 5.0**

**Total Findings:** 87
- **Critical:** 0
- **High:** 0
- **Medium:** 9
- **Low:** 13
- **Info:** 65

---

## Additional Observations

### Strengths

1. **State machine testing is exemplary.** The Tenant aggregate tests cover every valid and invalid state transition systematically, including idempotent operations and event payload verification. This is textbook DDD/ES aggregate testing.

2. **Auth middleware tests use real ASGI dispatch.** Rather than testing middleware methods in isolation, the tests build minimal Starlette apps and use TestClient, which exercises the full ASGI dispatch path including middleware ordering.

3. **Error handler coverage is production-grade.** Every domain exception type maps to a specific HTTP status with RFC 7807 problem details. Sensitive data sanitization (passwords, connection strings, tokens) is tested.

4. **ProjectionPoller testing is sophisticated.** The deterministic poll-loop testing pattern (using counted waits and direct `_poll_loop()` invocation) avoids flaky timing-dependent tests while still exercising the real polling logic.

5. **Provisioning service tests cover failure recovery.** The UserProvisioningService tests verify reservation release on save failure and race-condition retry logic, which are critical for correctness in distributed systems.

### Improvement Opportunities

1. **Consolidate mock-app factories.** `_make_mock_app()` appears in both `test_slug_registry.py` and `test_oidc_sub_registry.py` with identical structure. Consider a shared test utility module.

2. **Remove or utilize conftest fixtures.** The tenancy and identity conftest fixtures are defined but not used by any test file. Either remove them to reduce confusion or refactor test files to use them.

3. **Add multi-event projection replay tests.** While individual event handling is well-tested, no test replays a sequence (e.g., Provisioned -> Activated -> Suspended) to verify cumulative read model state.

4. **Consider marking smoke tests.** `tests/test_smoke.py` lacks pytest markers, making it unclear whether they should run with `make test-unit` or `make test-int`.

5. **Re-evaluate discovery test markers.** Tests in `test_discovery_integration.py` are marked `unit` but rely on real Python entry-point discovery from installed packages. These are more accurately integration tests.
