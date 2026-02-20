# Foundation & Infrastructure Tests -- Test Quality

**Collector ID:** 4A
**Dimension:** Test Quality
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. Pytest Markers

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

All three markers (`unit`, `integration`, `slow`) are registered in the root `pyproject.toml:120-124` with `--strict-markers` enabled (`pyproject.toml:128`), meaning unregistered markers will cause test failures. Every test across the foundation and infrastructure packages consistently uses `@pytest.mark.unit`.

Markers are applied at different granularities depending on the file: some use class-level markers (e.g., `packages/foundation-domain/tests/test_identifiers.py:12`, `packages/foundation-domain/tests/test_events.py:33`), while others apply the marker per-method within undecorated classes (e.g., `packages/foundation-application/tests/test_contributions.py:16`, `packages/foundation-application/tests/test_context.py:27`). This inconsistency is stylistic rather than functional.

**Findings:**

| File | Marker Style | Notes |
|------|-------------|-------|
| `packages/foundation-domain/tests/test_identifiers.py:12,94` | Class-level | Consistent within file |
| `packages/foundation-domain/tests/test_aggregates.py:25` | Class-level | Consistent |
| `packages/foundation-domain/tests/test_events.py:33,82,96,146` | Class-level | Consistent |
| `packages/foundation-domain/tests/test_value_objects.py:28,74,108,127,153,183,218,232,278` | Class-level | Consistent |
| `packages/foundation-domain/tests/test_exceptions.py:22,54,81,103,128,143,165,185,197` | Class-level | Consistent |
| `packages/foundation-domain/tests/test_ports.py:63,81` | Class-level | Consistent |
| `packages/foundation-domain/tests/test_principal.py:13,26` | Class-level | Consistent |
| `packages/foundation-domain/tests/test_config_value_objects.py:20,38,52,72,87,101,127,138` | Class-level | Consistent |
| `packages/foundation-application/tests/test_contributions.py:16,36,44,53,61,66,71` | Method-level | Mixed -- classes lack marker but methods have it |
| `packages/foundation-application/tests/test_discovery.py:11,19,27,33,40` | Method-level | Same pattern |
| `packages/foundation-application/tests/test_context.py:27,39,52,57,73,81,89,98,107,124,130,145,149,159,166` | Method-level | Same pattern |
| `packages/foundation-application/tests/test_config_service.py:53,61,65,69,78,88,104,119,128,157,167,177,191,201,210` | Method-level | Same pattern |
| `packages/infra-persistence/tests/test_database.py:17,27,34,49,59` | Method-level | Same pattern |
| `packages/infra-observability/tests/test_tracing.py:17,27,32,37,42,47,52,57,72,80` | Method-level | Same pattern |
| `packages/infra-taskiq/tests/test_broker.py:14,20,27,33,44` | Method-level | Same pattern |
| `packages/infra-eventsourcing/tests/test_settings.py:13` | Class-level (first), then `111,201` | Mixed |

- No `@pytest.mark.integration` tests exist among the in-scope packages (all tests are pure unit tests).
- The `@pytest.mark.slow` marker is registered but unused in these packages.
- Rating is 4 not 5 because of the inconsistent class-vs-method marker placement pattern.


## 2. Async Test Patterns

**Rating: 3/5 -- Defined**
**Severity:** Low | **Confidence:** High

The root `pyproject.toml:118` sets `asyncio_mode = "strict"`, which is correct and means all async tests require explicit `@pytest.mark.asyncio`. The `asyncio_default_fixture_loop_scope` is set to `"function"` (`pyproject.toml:119`), appropriate for test isolation.

However, there are **zero async tests** across all foundation and infrastructure test files examined. All 26 test files use synchronous test methods exclusively. This is acceptable for the foundation layer (pure domain logic), but the infrastructure layer has async production code (e.g., `redis_client.py` with `async def get_client()`, `async def close()`, and the observability `TraceContextMiddleware` ASGI middleware) that has no async test coverage.

**Findings:**

| Module with Async Production Code | Has Async Tests? |
|-----------------------------------|-----------------|
| `packages/infra-persistence/src/.../redis_client.py:111` (`async def get_client`) | No |
| `packages/infra-persistence/src/.../redis_client.py:141` (`async def close`) | No |
| `packages/infra-observability/src/.../middleware.py` (ASGI middleware) | No -- only tests class existence at `test_middleware.py:31` |
| `packages/infra-observability/src/.../instrumentation.py:135` (`async_wrapper`) | No |

- The strict async mode is properly configured but untested in practice.
- Rating is 3 because configuration is correct but async test coverage is absent where needed.


## 3. Fixture Quality

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Fixtures are used sparingly across the foundation and infrastructure tests. The root `tests/conftest.py` provides well-scoped function-level fixtures for integration tests (`dog_school_app`, `client`, `tenant_headers` at lines 27-48), each with explicit `@pytest.fixture()` scope (defaulting to function). These fixtures properly clean up state (`_dogs.clear()` at `tests/conftest.py:31,39`).

Foundation and infrastructure packages do not define their own `conftest.py` files (only `domain-identity` and `domain-tenancy` have package-level conftest files, which are out of scope). Instead, test helper functions are used inline (e.g., `_make_event` at `test_events.py:21`, `_make_key_generator` at `test_issue_api_key.py:16`, `_make_repo` at `test_config_service.py:31`, `_make_config_service` at `test_policy_binding.py:43`). These helper factory functions are a reasonable alternative but create duplication between test files.

**Findings:**

| Pattern | Location | Quality |
|---------|----------|---------|
| Root conftest fixtures | `tests/conftest.py:27-48` | Good -- function-scoped, cleanup on teardown |
| Helper factory `_make_event` | `test_events.py:21-30` | Good -- sensible defaults with override support |
| Helper factory `_make_key_generator` | `test_issue_api_key.py:16-25` | Adequate -- MagicMock factory, not Protocol-based |
| Helper factory `_make_app` | `test_issue_api_key.py:28-33` | Adequate -- MagicMock factory |
| Helper factory `_make_repo` | `test_config_service.py:31-49` | Good -- parameterized mock with behavior |
| Helper factory `_make_config_service` | `test_policy_binding.py:43-54` | Good -- parameterized mock with behavior |
| Helper factory `_make_config_service` | `test_resource_limits.py:23-27` | Adequate -- simple MagicMock |
| `TestPrincipalContext._make_principal` | `test_context.py:114-122` | Good -- encapsulates complex construction |
| `TestEventSourcingSettings._make_settings` | `test_settings.py:18-25` | Good -- defaults with overrides |

- No shared conftest within individual packages -- each test file is self-contained.
- No session-scoped or module-scoped fixtures used (appropriate for unit tests).
- Some `SYSTEM_DEFAULTS` mutation in `test_config_service.py` and `test_policy_binding.py` uses try/finally for cleanup rather than fixtures, which is fragile.


## 4. Mocking Strategy

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Mocking is done via `unittest.mock.MagicMock` and `unittest.mock.patch` throughout. The approach is generally reasonable -- mocks target dependencies (repositories, key generators, application services) rather than internal implementation details. However, Protocol-based test doubles are underutilized; only `test_ports.py` defines fake implementations that conform to Protocol interfaces.

**Findings:**

| File | Mocking Approach | Assessment |
|------|-----------------|------------|
| `test_issue_api_key.py:16-33` | `MagicMock` for APIKeyGeneratorPort and app | Mocks at port boundary, but untyped -- no Protocol conformance check |
| `test_rotate_api_key.py:17-34` | `MagicMock` for APIKeyGeneratorPort and app | Same pattern, duplicated from issue_api_key |
| `test_config_service.py:31-49` | `MagicMock` with behavioral `get`/`get_all` | Good -- behavior-based mock |
| `test_policy_binding.py:43-54` | `MagicMock` with behavioral `get_config` | Good -- behavior-based mock |
| `test_resource_limits.py:23-27` | `MagicMock` with `resolve_limit` | Adequate |
| `test_tenant_context.py:23-51` | `MagicMock(spec=Session)` | Good -- uses spec for type safety at `line 32` |
| `test_rls_helpers.py:20-85` | `patch("...rls_helpers.op")` | Mocks at Alembic boundary -- appropriate |
| `test_database.py:18-54` | `patch.dict("os.environ")` | Environment patching -- appropriate for settings |
| `test_tracing.py:19-86` | `patch.dict("os.environ")` | Same pattern |
| `test_logging.py:23-122` | `patch.dict("os.environ")` | Same pattern |
| `test_ports.py:16-60` | Protocol-conforming fakes | Best practice -- `_FakeLLMService`, `_FakeAPIKeyGenerator`, `_NotAPort` |

- `MagicMock` without `spec=` is the dominant pattern, meaning tests will not catch API mismatches at mock boundaries.
- Only `test_tenant_context.py:32` uses `MagicMock(spec=Session)` for type safety.
- Duplicated mock factories between `test_issue_api_key.py` and `test_rotate_api_key.py` (identical `_make_key_generator` and `_make_app` patterns).
- `test_tracing.py:38` and `test_logging.py:50` use bare `pytest.raises(Exception)` (with `# noqa: B017`), which is overly broad for testing validation errors.


## 5. Test Naming Conventions

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Test names broadly follow a `test_{scenario}` or `test_{method}_{scenario}` pattern. They are descriptive and convey intent. The codebase uses class-based grouping (`TestClassName`) to namespace related tests, which adds context to each test name.

**Findings:**

| Pattern | Examples | Quality |
|---------|----------|---------|
| `test_{valid_scenario}` | `test_valid_simple_slug` (`test_identifiers.py:16`), `test_valid_slug_with_hyphens` (`test_identifiers.py:20`) | Clear |
| `test_{rejects_invalid}` | `test_rejects_empty_string` (`test_identifiers.py:57`), `test_rejects_uppercase` (`test_identifiers.py:62`) | Clear |
| `test_{behavior}` | `test_frozen_immutability` (`test_identifiers.py:44`), `test_equality` (`test_identifiers.py:49`) | Clear |
| `test_{method}_{scenario}` | `test_handle_returns_key_id_and_full_key` (`test_issue_api_key.py:53`), `test_handle_calls_generate_extract_hash` (`test_issue_api_key.py:65`) | Descriptive |
| `test_{feature}_{condition}` | `test_boolean_feature_enabled` (`test_config_service.py:158`), `test_zero_percent_always_false` (`test_config_service.py:61`) | Clear |
| `test_{component}_{type}` | `test_broker_is_redis_stream_broker` (`test_broker.py:14`), `test_result_backend_is_redis` (`test_broker.py:20`) | Clear |

- No clear `test_{method}_{scenario}_{expected}` three-part convention, but the two-part naming is consistently descriptive.
- Class names provide meaningful grouping: `TestTenantId`, `TestBaseAggregate`, `TestDatabaseSettings`, etc.
- Rating is 4 because naming is consistently descriptive even though it doesn't follow a strict three-part convention.


## 6. Assertion Quality

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Assertions are specific and generally test one logical thing per test method. `pytest.raises` is used with `match=` for error message verification in most cases. `pytest.approx` is used for float comparisons (`test_config_value_objects.py:79,83,84`).

**Findings:**

| Pattern | Examples | Quality |
|---------|----------|---------|
| Specific value assertions | `assert tid.value == "acme"` (`test_identifiers.py:18`) | Good |
| Error message matching | `pytest.raises(ValueError, match="Invalid tenant ID format")` (`test_identifiers.py:58`) | Good |
| Type checking assertions | `assert isinstance(PrincipalType.USER, str)` (`test_principal.py:23`) | Good |
| Float comparison | `assert v.value == pytest.approx(3.14)` (`test_config_value_objects.py:79`) | Good |
| Broad exception catching | `pytest.raises(Exception)` (`test_redis_settings.py:67`, `test_tracing.py:38`, `test_logging.py:50`) | Poor -- catches anything, with `# noqa: B017` suppression |
| Behavioral assertions | `gen.generate_api_key.assert_called_once()` (`test_issue_api_key.py:73`) | Good |
| Context dict assertions | `assert err.context["tenant_id"] == "acme"` (`test_exceptions.py:75`) | Good |
| Weak assertion | `assert logger is not None` (`test_logging.py:116,122`) | Weak -- only checks existence, not type |

- 3 instances of bare `pytest.raises(Exception)` suppress Ruff B017 with `# noqa` comments: `test_redis_settings.py:67`, `test_tracing.py:38`, `test_logging.py:50`.
- `test_logging.py:101-107` has two tests that assert nothing -- merely that no exception is raised. Comments like "no exception means success" are not rigorous.
- `test_middleware.py:31-32` asserts `isinstance(TraceContextMiddleware, type)` which is trivially true for any class.


## 7. Edge Case Coverage

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Foundation domain tests demonstrate thorough edge case testing, especially for value objects and identifiers. Boundary values, empty inputs, None-equivalent cases, and error paths are well-covered.

**Findings:**

| Category | Examples | Coverage |
|----------|----------|----------|
| Empty strings | `test_rejects_empty_string` (`test_identifiers.py:57`), `test_rejects_empty` (`test_value_objects.py:48-49`) | Thorough |
| Boundary lengths | `test_valid_minimum_length` (`test_value_objects.py:36`), `test_valid_max_length` (`test_value_objects.py:40`), `test_rejects_too_long` (`test_value_objects.py:53`) | Thorough |
| Whitespace handling | `test_strips_whitespace` (`test_value_objects.py:82`), `test_rejects_whitespace_only` (`test_value_objects.py:90`) | Thorough |
| Format violations | Uppercase, underscores, leading/trailing hyphens, consecutive hyphens, special chars, dots in `test_identifiers.py:62-91` | Thorough |
| Immutability | `test_frozen_immutability` across all value objects | Thorough |
| Percent boundaries | `test_zero_percent_always_false` (`test_config_service.py:62`), `test_hundred_percent_always_true` (`test_config_service.py:66`) | Good |
| Missing config fallback | `test_no_config_returns_false` (`test_config_service.py:191`), `test_returns_none_for_unknown_key` (`test_config_service.py:120`) | Good |
| Port validation | `test_port_validation_lower_bound` (`test_settings.py:81`), `test_port_validation_upper_bound` (`test_settings.py:85`), `test_port_valid_boundaries` (`test_settings.py:89`) | Good |
| Pool size bounds | `test_pool_size_validation` (`test_settings.py:96-98`), `test_max_overflow_validation` (`test_settings.py:103-108`) | Good |
| Missing context | `test_get_raises_when_no_context` (`test_context.py:52`), `test_tenant_id_raises_without_context` (`test_context.py:98`) | Good |
| Idempotent shutdown | `test_shutdown_idempotent` (`test_tracing.py:72-75`) | Good |
| URL validation | `test_from_url_invalid_scheme` (`test_redis_settings.py:56`), `test_from_url_invalid_db_number` (`test_redis_settings.py:61`) | Good |

- Missing edge case: no test for `Email("")` being valid alongside `Email("notanemail")` being invalid -- this empty-string-is-valid behavior at `test_value_objects.py:161-162` seems like it could be a bug that should be tested more rigorously.
- No null/None input tests for value object constructors (e.g., `TenantId(None)` -- would this raise `TypeError` or `ValueError`?).
- Redis settings `test_validate_port_invalid` at `test_redis_settings.py:66-68` uses only `redis_port=0` but doesn't test `redis_port=65536` or negative.


## 8. Test Organization

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Tests mirror source structure well. Each source module in the foundation and infrastructure packages has a corresponding test file. Tests are organized into logical classes that group related assertions.

**Findings:**

| Source Module | Test File | Match |
|---------------|-----------|-------|
| `foundation/domain/identifiers.py` | `test_identifiers.py` | Yes |
| `foundation/domain/principal.py` | `test_principal.py` | Yes |
| `foundation/domain/aggregates.py` | `test_aggregates.py` | Yes |
| `foundation/domain/events.py` | `test_events.py` | Yes |
| `foundation/domain/exceptions.py` | `test_exceptions.py` | Yes |
| `foundation/domain/config_value_objects.py` | `test_config_value_objects.py` | Yes |
| `foundation/domain/{tenant,user,agent}_value_objects.py` | `test_value_objects.py` | Combined file -- acceptable |
| `foundation/domain/ports/*.py` | `test_ports.py` | Combined file -- acceptable |
| `foundation/domain/policy_types.py` | No dedicated test file | Tested indirectly via `test_policy_binding.py` |
| `foundation/domain/config_defaults.py` | No dedicated test file | Tested indirectly via `test_config_service.py` |
| `foundation/application/context.py` | `test_context.py` | Yes |
| `foundation/application/config_service.py` | `test_config_service.py` | Yes |
| `foundation/application/contributions.py` | `test_contributions.py` | Yes |
| `foundation/application/discovery.py` | `test_discovery.py` | Yes |
| `foundation/application/issue_api_key.py` | `test_issue_api_key.py` | Yes |
| `foundation/application/rotate_api_key.py` | `test_rotate_api_key.py` | Yes |
| `foundation/application/policy_binding.py` | `test_policy_binding.py` | Yes |
| `foundation/application/resource_limits.py` | `test_resource_limits.py` | Yes |
| `infra/persistence/database.py` | `test_database.py` | Yes |
| `infra/persistence/redis_settings.py` | `test_redis_settings.py` | Yes |
| `infra/persistence/redis_client.py` | No test file | Gap |
| `infra/persistence/tenant_context.py` | `test_tenant_context.py` | Yes |
| `infra/persistence/rls_helpers.py` | `test_rls_helpers.py` | Yes |
| `infra/observability/logging.py` | `test_logging.py` | Yes |
| `infra/observability/tracing.py` | `test_tracing.py` | Yes |
| `infra/observability/middleware.py` | `test_middleware.py` | Yes |
| `infra/observability/instrumentation.py` | No test file | Gap |
| `infra/taskiq/broker.py` | `test_broker.py` | Yes |

- All tests reside under `packages/{name}/tests/` directly (flat layout), which is appropriate given the small number of test files per package.
- All foundation and infrastructure tests are unit tests only -- no integration test files exist within these packages.
- Root `testpaths` configuration (`pyproject.toml:116`) correctly discovers both `tests/` and `packages/*/tests/`.


## 9. Foundation Domain Tests

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Foundation domain tests comprehensively cover the core domain primitives. All major categories are tested: aggregates, events, value objects, identifiers, exceptions, and port protocols.

**Findings:**

| Component | Test File | Tests | Assessment |
|-----------|-----------|-------|------------|
| `BaseAggregate` | `test_aggregates.py:26-59` | 7 tests | Covers creation, versioning, event collection, ID, inheritance. Missing: multi-tenant isolation, error handling |
| `BaseEvent` | `test_events.py:34-153` | 17 tests | Thorough -- tenant validation, `get_topic()`, `to_dict()`, immutability, optional fields |
| `TenantId` / `UserId` | `test_identifiers.py:12-121` | 19 tests | Thorough -- valid/invalid formats, equality, immutability, string conversion |
| `Principal` | `test_principal.py:13-77` | 9 tests | Covers construction, defaults, immutability, equality |
| `TenantSlug/Name/Status` | `test_value_objects.py:28-119` | 15 tests | Thorough edge cases and validation |
| `OidcSub/Email/DisplayName` | `test_value_objects.py:128-210` | 14 tests | Good coverage including whitespace handling |
| `AgentStatus/AgentTypeId/APIKeyMetadata` | `test_value_objects.py:218-302` | 14 tests | Covers enums, validation, immutability |
| `ConfigKey` and config values | `test_config_value_objects.py:20-170` | 18 tests | Covers all 6 value types, discriminated union, extensibility |
| `DomainError` hierarchy | `test_exceptions.py:22-221` | 30 tests | Thorough -- all 8 exception types tested for code, message, context, inheritance |
| Port protocols | `test_ports.py:63-113` | 9 tests | Covers `LLMServicePort`, `APIKeyGeneratorPort`, runtime checking, non-conforming rejection |
| `PolicyType` | No dedicated test | 0 | Only tested indirectly as base class in `test_policy_binding.py` |
| `config_defaults.py` | No dedicated test | 0 | Only tested as side effect in other tests |

- Total: ~152 tests across 8 files covering the foundation domain.
- Gap: `PolicyType` and `config_defaults` have no dedicated tests, but both are minimal (empty StrEnum and single dict respectively).
- Minor gap: `BaseAggregate` tests use only a single `Dog` test aggregate and don't test tenant isolation or error paths.


## 10. Foundation Application Tests

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Foundation application tests cover all 8 source modules (excluding `__init__.py`). Context propagation, config service, resource limits, policy binding, contributions, discovery, and API key handlers are all tested.

**Findings:**

| Component | Test File | Tests | Assessment |
|-----------|-----------|-------|------------|
| `RequestContext` + `PrincipalContext` | `test_context.py:26-171` | 17 tests | Thorough -- lifecycle, isolation, error states, optional principal |
| `TenantConfigService` | `test_config_service.py:52-214` | 12 tests | Good -- override precedence, fallback, missing keys, feature flags, percentage flags, resolve_limit |
| `ResourceLimitService` | `test_resource_limits.py:30-110` | 8 tests | Good -- under limit, exceeded, unknown resource, custom increment, injectable map |
| `PolicyBindingService` | `test_policy_binding.py:57-184` | 8 tests | Good -- resolution precedence, fallback, missing, unsupported, injectable registry |
| `MiddlewareContribution` | `test_contributions.py:15-39` | 4 tests | Covers defaults, custom values, immutability |
| `ErrorHandlerContribution` | `test_contributions.py:42-56` | 2 tests | Covers storage and immutability |
| `LifespanContribution` | `test_contributions.py:59-74` | 3 tests | Covers defaults, custom priority, immutability |
| `discover()` | `test_discovery.py:10-46` | 4 tests | Covers empty group, return type, exclude_names |
| `IssueAPIKeyHandler` | `test_issue_api_key.py:36-119` | 7 tests | Thorough -- return values, call verification, DI |
| `RotateAPIKeyHandler` | `test_rotate_api_key.py:37-139` | 7 tests | Thorough -- mirrors issue handler pattern |

- Total: ~72 tests across 8 files covering the foundation application.
- Good test isolation: `test_context.py:160-171` explicitly verifies no state leakage between tests.
- SYSTEM_DEFAULTS mutation in `test_config_service.py` and `test_policy_binding.py` uses try/finally blocks rather than fixtures for cleanup, which could leave state if an unexpected exception type is raised.
- Missing: no tests for concurrent context access or thread safety of context variables.


## 11. Infrastructure Persistence Tests

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Infrastructure persistence tests cover 4 of 5 source modules. The `redis_client.py` module (containing `RedisFactory` and `get_redis_factory()`) has no test coverage at all. Existing tests focus on settings/configuration and mock-based unit testing of SQL helpers.

**Findings:**

| Component | Test File | Tests | Assessment |
|-----------|-----------|-------|------------|
| `DatabaseSettings` | `test_database.py:15-62` | 5 tests | Covers defaults, URL construction, env vars, repr |
| `_get_database_url` | `test_database.py:57-62` | 1 test | Minimal -- only checks prefix |
| `RedisSettings` | `test_redis_settings.py:12-74` | 10 tests | Good -- defaults, URL construction, password, from_url, validation |
| `RedisFactory` / `get_redis_factory` | No test file | 0 tests | **Gap** -- async factory, get_client, close, from_env, from_url untested |
| `_set_tenant_context_on_begin` | `test_tenant_context.py:22-70` | 3 tests | Good -- context available, missing, empty tenant |
| `register_tenant_context_handler` | `test_tenant_context.py:73-79` | 1 test | Adequate -- verifies event listener registration |
| `enable_rls` / `disable_rls` | `test_rls_helpers.py:17-42` | 3 tests | Good -- with and without force, disable |
| `create_tenant_isolation_policy` | `test_rls_helpers.py:45-67` | 3 tests | Good -- default name, cast type, custom name |
| `drop_tenant_isolation_policy` | `test_rls_helpers.py:70-85` | 2 tests | Good -- default and custom name |

- Total: ~28 tests across 4 files.
- **Critical gap**: `redis_client.py` has 168 lines including a factory class, async methods, and a cached singleton -- entirely untested.
- No integration tests exist to verify actual database connections or migrations.
- `test_database.py:54` has a weak assertion: `assert "postgres" not in repr_str or "password" not in repr_str` -- this OR condition means the test passes even if the password IS visible in repr (as long as the string "postgres" is absent).


## 12. Infrastructure Observability & TaskIQ Tests

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Observability tests cover logging, tracing settings, and middleware contribution. However, the `instrumentation.py` module (containing `traced_operation` decorator, `start_span` context manager, and helper functions) has zero test coverage. TaskIQ tests exist but are minimal.

**Findings:**

| Component | Test File | Tests | Assessment |
|-----------|-----------|-------|------------|
| `LoggingSettings` | `test_logging.py:21-59` | 7 tests | Good -- defaults, JSON mode, level parsing, env vars |
| `SensitiveDataProcessor` | `test_logging.py:62-92` | 4 tests | Good -- exact match, substring, non-sensitive, case insensitive |
| `configure_logging` | `test_logging.py:95-107` | 2 tests | Weak -- no assertions, just "no exception" |
| `get_logger` | `test_logging.py:110-122` | 2 tests | Weak -- only `assert logger is not None` |
| `TracingSettings` | `test_tracing.py:16-67` | 8 tests | Good -- defaults, enabled state, normalization, headers, env vars |
| `shutdown_tracing` | `test_tracing.py:70-75` | 1 test | Adequate -- idempotent shutdown |
| `get_tracing_settings` | `test_tracing.py:78-86` | 1 test | Good -- caching verification |
| `TraceContextMiddleware` contribution | `test_middleware.py:14-32` | 4 tests | Minimal -- only tests contribution metadata and class existence |
| `instrumentation.py` (traced_operation, start_span, etc.) | No test file | 0 tests | **Gap** -- 214 lines untested |
| `broker` (RedisStreamBroker) | `test_broker.py:12-48` | 5 tests | Adequate -- type checks, env URL |
| `result_backend` | `test_broker.py:20-23` | 1 test | Minimal -- type check only |
| `scheduler` | `test_broker.py:27-29` | 1 test | Minimal -- type check only |
| `_get_redis_url` | `test_broker.py:33-48` | 2 tests | Good -- env override and default |

- Total: ~38 tests across 4 files.
- **Major gap**: `instrumentation.py` with `traced_operation` decorator, `start_span` context manager, `get_tracer`, `get_current_span`, and `set_span_error` -- all untested (214 lines of code).
- TaskIQ tests only verify object types at import time; no behavioral testing of broker configuration, task registration, or scheduler behavior.
- `test_middleware.py` only validates metadata; no ASGI dispatch testing.
- `test_logging.py:97-107` has two tests with zero meaningful assertions.


## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | Pytest Markers | 4/5 | Low |
| 2 | Async Test Patterns | 3/5 | Low |
| 3 | Fixture Quality | 3/5 | Medium |
| 4 | Mocking Strategy | 3/5 | Medium |
| 5 | Test Naming Conventions | 4/5 | Low |
| 6 | Assertion Quality | 4/5 | Low |
| 7 | Edge Case Coverage | 4/5 | Low |
| 8 | Test Organization | 4/5 | Low |
| 9 | Foundation Domain Tests | 4/5 | Low |
| 10 | Foundation Application Tests | 4/5 | Low |
| 11 | Infrastructure Persistence Tests | 3/5 | Medium |
| 12 | Infrastructure Observability & TaskIQ Tests | 3/5 | Medium |

**Overall weighted average: 3.6/5**

**Key gaps requiring attention:**
1. `packages/infra-persistence/src/.../redis_client.py` -- completely untested async factory (168 LOC)
2. `packages/infra-observability/src/.../instrumentation.py` -- completely untested tracing utilities (214 LOC)
3. Zero async tests across all foundation/infrastructure packages despite async production code
4. Predominant use of untyped `MagicMock` without `spec=` parameter across application tests
