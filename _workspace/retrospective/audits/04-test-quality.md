# Dimension 4: Test Quality

**RAG Status:** AMBER
**Average Maturity:** 3.9/5
**Date:** 2026-02-18

## Executive Summary

The Praecepta monorepo demonstrates strong test quality at the domain and integration layers, with exemplary state-machine testing for aggregates, comprehensive auth middleware coverage using real ASGI dispatch, and production-grade error handler verification including RFC 7807 compliance and sensitive data sanitization. The domain packages (tenancy, identity) and the FastAPI integration layer consistently achieve maturity ratings of 4-5, reflecting mature, well-structured test suites that cover happy paths, error scenarios, idempotent operations, and audit metadata propagation.

However, the foundation and infrastructure layers reveal structural gaps that pull the overall maturity below the GREEN threshold. Two significant modules -- `redis_client.py` (168 LOC) and `instrumentation.py` (214 LOC) -- have zero test coverage. Async production code across all infrastructure packages is never tested with async test functions; instead, all async behavior is exercised indirectly through synchronous TestClient wrappers. The predominant use of untyped `MagicMock` (without `spec=`) means mock boundaries do not enforce API contracts, creating a class of bugs that tests cannot catch.

The combined average maturity of 3.9/5 across 24 checklist items, with 70.8% of items rated 4 or above, places this dimension solidly in AMBER territory. There are no Critical or High severity findings. The nine Medium-severity findings cluster around three themes: untested infrastructure modules, dead fixture code, and the absence of direct async testing. Addressing these gaps would raise the average above 4.0 and move the dimension to GREEN.

## Consolidated Checklist

| # | Area | Item | Rating | Severity | Source |
|---|------|------|--------|----------|--------|
| 1 | Test Infrastructure | Pytest Markers | 4/5 | Low | 4A |
| 2 | Test Infrastructure | Async Test Patterns | 3/5 | Low | 4A |
| 3 | Test Infrastructure | Fixture Quality | 3/5 | Medium | 4A |
| 4 | Test Infrastructure | Mocking Strategy | 3/5 | Medium | 4A |
| 5 | Test Craft | Test Naming Conventions | 4/5 | Low | 4A |
| 6 | Test Craft | Assertion Quality | 4/5 | Low | 4A |
| 7 | Test Craft | Edge Case Coverage | 4/5 | Low | 4A |
| 8 | Test Craft | Test Organization | 4/5 | Low | 4A |
| 9 | Layer Tests | Foundation Domain Tests | 4/5 | Low | 4A |
| 10 | Layer Tests | Foundation Application Tests | 4/5 | Low | 4A |
| 11 | Layer Tests | Infrastructure Persistence Tests | 3/5 | Medium | 4A |
| 12 | Layer Tests | Infrastructure Observability & TaskIQ Tests | 3/5 | Medium | 4A |
| 13 | Domain Tests | Domain Aggregate Event Tests | 5/5 | Info | 4B |
| 14 | Domain Tests | Projection Tests | 5/5 | Medium | 4B |
| 15 | Domain Tests | Auth Middleware Tests | 5/5 | Low | 4B |
| 16 | Domain Tests | FastAPI Integration Tests | 5/5 | Low | 4B |
| 17 | Integration Tests | Root Integration Tests | 4/5 | Medium | 4B |
| 18 | Test Infrastructure | Fixtures Reuse | 4/5 | Medium | 4B |
| 19 | Test Infrastructure | Test Data Factories | 3/5 | Medium | 4B |
| 20 | Test Infrastructure | Async Integration | 3/5 | Medium | 4B |
| 21 | Domain Tests | Error Scenario Coverage | 5/5 | Info | 4B |
| 22 | Layer Tests | Event Sourcing Tests | 4/5 | Medium | 4B |
| 23 | Test Infrastructure | Marker Consistency | 4/5 | Medium | 4B |
| 24 | Test Craft | Test Documentation | 4/5 | Low | 4B |

**RAG Calculation:**
- Critical findings: 0 | High findings: 0
- Average maturity: (4+3+3+3+4+4+4+4+4+4+3+3+5+5+5+5+4+4+3+3+5+4+4+4) / 24 = 94 / 24 = 3.917 (rounds to 3.9)
- Items at 4+: 17 / 24 = 70.8%
- Items at 3+: 24 / 24 = 100%
- GREEN requires avg >= 4.0 AND >= 80% at 4+ -- **fails** (3.9 < 4.0, 70.8% < 80%)
- AMBER requires avg >= 3.0 AND <= 2 High AND >= 60% at 3+ -- **passes**

## Critical & High Findings

None. There are zero Critical or High severity findings across both collector reports.

## Medium Findings

**M1. `redis_client.py` entirely untested (168 LOC)**
`packages/infra-persistence/src/.../redis_client.py` contains `RedisFactory`, `get_redis_factory()`, `async def get_client()`, `async def close()`, `from_env()`, and `from_url()` -- all without any test coverage. This is an async factory with a cached singleton pattern, making it particularly important to test.
Source: 4A (Item 11) | Ref: `packages/infra-persistence/src/.../redis_client.py:111,141`

**M2. `instrumentation.py` entirely untested (214 LOC)**
`packages/infra-observability/src/.../instrumentation.py` contains `traced_operation` decorator, `start_span` context manager, `get_tracer`, `get_current_span`, `set_span_error`, and `async_wrapper` -- all without any test coverage. This is core observability infrastructure.
Source: 4A (Item 12) | Ref: `packages/infra-observability/src/.../instrumentation.py:135`

**M3. Zero direct async test functions across the entire codebase**
Despite `asyncio_mode = "strict"` being configured in `pyproject.toml:118` and production code containing async methods (Redis client, ASGI middleware, observability wrappers), no test file contains `async def test_*` functions. All async behavior is tested indirectly through synchronous TestClient.
Source: 4A (Item 2), 4B (Item 8) | Ref: `pyproject.toml:118-119`, all test files

**M4. Conftest fixtures defined but unused (dead code)**
Both `packages/domain-tenancy/tests/conftest.py` and `packages/domain-identity/tests/conftest.py` define fixtures (`new_tenant`, `active_tenant`, `suspended_tenant`, `decommissioned_tenant`, `user`, `agent`) that are not used by any test file. All aggregate tests use inline helper functions instead.
Source: 4B (Items 6, 7) | Ref: `packages/domain-tenancy/tests/conftest.py` (entire file), `packages/domain-identity/tests/conftest.py` (entire file)

**M5. Untyped `MagicMock` without `spec=` is the dominant mocking pattern**
Across foundation-application and infrastructure tests, `MagicMock()` is used without the `spec=` parameter, meaning mocks will silently accept any attribute access or method call regardless of the real interface. Only `test_tenant_context.py:32` uses `MagicMock(spec=Session)`, and only `test_ports.py` uses Protocol-conforming fakes.
Source: 4A (Item 4) | Ref: `test_issue_api_key.py:16-33`, `test_rotate_api_key.py:17-34`, `test_config_service.py:31-49`, `test_resource_limits.py:23-27`

**M6. No projection multi-event sequence replay tests**
Projection tests dispatch individual events in isolation. No test replays a sequence of events (e.g., Provisioned -> Activated -> Suspended) to verify the cumulative read model state, which is the primary correctness property of projections.
Source: 4B (Item 2) | Ref: `packages/domain-tenancy/tests/test_tenant_list_projection.py` (entire file)

**M7. Auth stack and event store excluded from integration fixtures**
Root-level integration tests exclude auth middleware and the event store from the Dog School app fixture, meaning no integration test exercises the full authenticated request path or event persistence round-trip.
Source: 4B (Item 5) | Ref: `tests/conftest.py:16-23`, `tests/conftest.py:19`

**M8. Smoke tests lack pytest markers**
`tests/test_smoke.py:10-51` verifies all 11 packages are importable but carries no `@pytest.mark.unit` or `@pytest.mark.integration` marker, making it unclear which test suite they belong to.
Source: 4B (Item 11) | Ref: `tests/test_smoke.py:10-51`

**M9. Duplicated mock-app factory helpers across packages**
`_make_mock_app()` is duplicated between `packages/domain-tenancy/tests/test_slug_registry.py:14-24` and `packages/domain-identity/tests/test_oidc_sub_registry.py:14-25` with identical structure. Similarly, `_make_key_generator` and `_make_app` patterns are duplicated between `test_issue_api_key.py` and `test_rotate_api_key.py`.
Source: 4A (Item 4), 4B (Item 7) | Ref: `packages/domain-tenancy/tests/test_slug_registry.py:14-24`, `packages/domain-identity/tests/test_oidc_sub_registry.py:14-25`, `test_issue_api_key.py:16-33`, `test_rotate_api_key.py:17-34`

## Low & Info Findings

**Low severity findings (consolidated):**

- Inconsistent marker placement: foundation-domain uses class-level markers while foundation-application uses method-level markers (4A Item 1). The FastAPI error handler tests also use method-level markers (4B Item 11).
- Three instances of bare `pytest.raises(Exception)` with `# noqa: B017` suppression at `test_redis_settings.py:67`, `test_tracing.py:38`, `test_logging.py:50` (4A Item 6).
- Weak assertions: `assert logger is not None` at `test_logging.py:116,122`; `isinstance(TraceContextMiddleware, type)` at `test_middleware.py:31-32` (4A Item 6).
- Two `configure_logging` tests with zero meaningful assertions at `test_logging.py:101-107` (4A Item 12).
- Event types asserted by string comparison (`__class__.__name__`) rather than importing domain event types at `test_tenant.py:97`, `test_user.py:45` (4B Item 1).
- No explicit JWT expired-token test scenario (4B Item 3).
- No test for concurrent/parallel request handling in integration tests (4B Item 5).
- Discovery integration tests marked `unit` despite exercising real entry-point discovery at `packages/infra-fastapi/tests/test_discovery_integration.py:13-14` (4B Item 11).
- Minor documentation gaps in simple test classes missing docstrings (4B Item 12).
- Missing edge cases: no `TenantId(None)` test, no `redis_port=65536` boundary test, `Email("")` validity not rigorously explored (4A Item 7).
- Weak database repr test: OR condition at `test_database.py:54` allows password visibility (4A Item 11).
- `test_tenant.py` and `test_user.py` use inline helpers instead of available conftest fixtures (4B Item 6).
- Session factory helpers have slightly different patterns between `test_tenant_repository.py:12-23` and `test_config_repository.py:14-30` (4B Item 7).

**Info findings:** 65 informational findings across both collectors documenting correct behaviors, thorough test coverage, and well-structured test patterns. These validate the strengths of the test suite rather than identifying problems.

## Cross-Cutting Themes

**1. Async testing gap across all layers.** Both collectors independently identified that despite `asyncio_mode = "strict"` configuration and async production code in persistence, observability, and ASGI middleware, zero async test functions exist. Collector 4A noted the infrastructure async gap; Collector 4B noted the domain/integration async gap. This is the single most pervasive theme -- the framework has async infrastructure that is only tested indirectly.

**2. Test doubles lack type safety.** Both collectors found that mocks predominantly use untyped `MagicMock()` rather than `spec=`-based mocks or Protocol-conforming fakes. Collector 4A identified this in foundation-application tests; Collector 4B identified duplicated mock factories across domain packages. The only exceptions are `test_ports.py` (Protocol fakes) and `test_tenant_context.py` (spec-based mock). This means API contract violations between production code and its mocks cannot be detected by tests.

**3. Defined-but-unused test infrastructure.** Both collectors identified fixtures and helpers that are defined but not consumed. Collector 4A noted the absence of package-level conftest files in foundation/infrastructure packages (with inline helpers used instead). Collector 4B found that domain-tenancy and domain-identity conftest fixtures are defined but entirely unused. The codebase has a pattern of preferring per-file helper functions over shared fixtures, which is defensible but creates duplication and dead code.

**4. Infrastructure modules with zero coverage alongside exemplary domain tests.** The quality distribution is bimodal: domain aggregate tests, projection tests, auth middleware tests, and error handler tests achieve maturity 5/5, while infrastructure utility modules (`redis_client.py`, `instrumentation.py`) and infrastructure behavioral tests (TaskIQ broker, observability middleware) sit at 3/5 with significant gaps. The test investment has prioritized business logic correctness over infrastructure plumbing.

## Strengths

1. **State machine testing is exemplary.** The Tenant aggregate tests systematically cover every valid and invalid state transition (provisioned, active, suspended, decommissioned), including idempotent operations and audit metadata on every event. This is textbook DDD/ES aggregate testing. Ref: `packages/domain-tenancy/tests/test_tenant.py:93-611`.

2. **Auth middleware tests use real ASGI dispatch.** Rather than testing middleware methods in isolation, auth tests build minimal Starlette applications and exercise the full middleware stack through TestClient. API key tests use real cryptographic hashing via `APIKeyGenerator`. Ref: `packages/infra-auth/tests/test_jwt_auth_middleware.py`, `packages/infra-auth/tests/test_api_key_auth_middleware.py`.

3. **Error handler coverage is production-grade.** Every domain exception type maps to a specific HTTP status with RFC 7807 problem detail responses. Sensitive data sanitization (passwords, connection strings, UUIDs, tokens) is tested explicitly. Content-type `application/problem+json` is verified. Ref: `packages/infra-fastapi/tests/test_error_handlers.py:46-386`.

4. **Edge case coverage in foundation domain is thorough.** Value objects test empty strings, boundary lengths, whitespace handling, format violations, immutability, and type coercion. Config service tests cover zero-percent and hundred-percent rollout flags, missing keys, override precedence, and fallback behavior. Ref: `packages/foundation-domain/tests/test_value_objects.py`, `packages/foundation-domain/tests/test_identifiers.py`, `packages/foundation-application/tests/test_config_service.py`.

5. **ProjectionPoller testing uses deterministic patterns.** The poller tests avoid flaky timing-dependent behavior by using counted waits and direct `_poll_loop()` invocation, covering lifecycle management, error recovery, stop-event propagation, and multi-projection processing. Ref: `packages/infra-eventsourcing/tests/test_projection_poller.py:74-385`.

## Recommendations

**P1 -- Add tests for untested infrastructure modules**
Write unit tests for `packages/infra-persistence/src/.../redis_client.py` (168 LOC) and `packages/infra-observability/src/.../instrumentation.py` (214 LOC). These are the only two source modules with zero test coverage. Focus on the `RedisFactory` singleton lifecycle, `traced_operation` decorator behavior, and `start_span` context manager. This directly addresses M1 and M2.

**P1 -- Introduce async test functions for infrastructure async code**
Add `@pytest.mark.asyncio` tests for `redis_client.py` async methods (`get_client`, `close`), the `async_wrapper` in instrumentation, and at least one direct async middleware dispatch test. The `asyncio_mode = "strict"` configuration is already in place but entirely unused. This addresses M3.

**P2 -- Add `spec=` to MagicMock usage or migrate to Protocol fakes**
Audit all `MagicMock()` usages and add `spec=<TargetClass>` where the target type is available. For port-boundary mocks, follow the pattern established in `test_ports.py` using Protocol-conforming fakes. This addresses M5 and improves contract safety across all mock boundaries.

**P2 -- Add projection multi-event replay tests**
For each projection, add at least one test that dispatches a sequence of events (e.g., Provisioned -> Activated -> Suspended) and verifies the cumulative read model state. This validates the primary correctness property of projections. This addresses M6.

**P2 -- Clean up dead conftest fixtures or refactor tests to use them**
Either remove the unused fixtures in `packages/domain-tenancy/tests/conftest.py` and `packages/domain-identity/tests/conftest.py`, or refactor aggregate test files to use them instead of inline helpers. Dead code in test infrastructure creates confusion about intended patterns. This addresses M4.

**P3 -- Add pytest markers to smoke tests**
Add `@pytest.mark.unit` (or a dedicated `@pytest.mark.smoke` marker registered in `pyproject.toml`) to `tests/test_smoke.py` so these tests are included in the correct test suite filter. This addresses M8.

**P3 -- Consolidate duplicated mock factories into shared test utilities**
Extract `_make_mock_app()` and similar duplicated helpers into a shared test utility module (e.g., `tests/_helpers.py` or a conftest at the appropriate level) to reduce duplication and ensure consistency. This addresses M9.

**P3 -- Standardize marker placement (class-level vs method-level)**
Adopt a consistent convention for pytest marker placement -- class-level is preferred for grouping -- and apply it uniformly across all packages. This is a stylistic improvement that reduces cognitive overhead. This addresses the Low finding from Items 1 and 23.

**P3 -- Replace bare `pytest.raises(Exception)` with specific exception types**
The three instances at `test_redis_settings.py:67`, `test_tracing.py:38`, and `test_logging.py:50` should catch `ValidationError` or the specific expected exception type rather than the base `Exception` class with a `# noqa: B017` suppression.
