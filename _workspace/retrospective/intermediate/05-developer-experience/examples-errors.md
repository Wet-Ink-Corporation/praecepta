# Examples & Error Messages -- Developer Experience

**Collector ID:** 5C
**Dimension:** Developer Experience
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. Dog School Example Completeness

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

The `examples/dog_school/` example is a complete, runnable application that demonstrates key framework patterns: aggregate definition with event sourcing, REST API router creation, app factory usage with auto-discovery, and multi-tenancy via request context. It includes four well-structured files:

- `examples/dog_school/__init__.py:1-16` -- Module docstring explains the example, exports key symbols.
- `examples/dog_school/domain.py:1-49` -- Defines `Dog` aggregate with `@event` decorators, `ValidationError` for duplicate tricks, custom `DogNotFoundError`.
- `examples/dog_school/router.py:1-84` -- Three REST endpoints (register, get, learn trick), Pydantic request/response models.
- `examples/dog_school/app.py:1-55` -- App factory using `create_app()` with `exclude_names` for external services.

The example successfully demonstrates: aggregate creation with event sourcing, command validation pattern, custom domain exceptions, in-memory store (explicitly noted as development placeholder at `router.py:20`), and the zero-manual-wiring app factory pattern.

**Findings:**

| Aspect | Status | Detail |
|--------|--------|--------|
| Runnable | Yes | TestClient-based tests pass (`tests/test_integration_dog_school.py`) |
| Aggregate pattern | Yes | Two-method command pattern at `domain.py:24-41` |
| Event sourcing | Yes | `@event("Registered")` and `@event("TrickAdded")` decorators |
| REST API | Yes | POST/GET endpoints with Pydantic DTOs |
| Error handling | Yes | `DogNotFoundError` and `ValidationError` demonstrated |
| Multi-tenancy | Yes | `get_current_tenant_id()` at `router.py:49` |
| Auth | No | Auth is excluded via `_DEFAULT_EXCLUDE_NAMES` at `app.py:26-33` |
| Projections | No | No projection example included |
| Standalone run instructions | No | No `uvicorn` command or `__main__.py` |

## 2. Example Code Quality

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The example code is well-structured, idiomatic Python 3.12+, and consistently follows the project's code style. Each file has a module-level docstring explaining its purpose. The code uses type hints, `from __future__ import annotations`, and Pydantic `BaseModel` correctly.

**Findings:**

| Quality Aspect | Rating | Reference |
|----------------|--------|-----------|
| Module docstrings | Excellent | All four files have descriptive module docstrings |
| Inline comments | Good | `router.py:20` explains in-memory store; `app.py:25` explains exclusions |
| Type annotations | Good | Full type hints on all functions and return types |
| Section separators | Good | `router.py:24,44,74` uses comment headers for logical sections |
| Docstrings on functions | Good | `domain.py:30-35` documents `add_trick` with `Raises:` section |
| Code organization | Excellent | Clean separation of domain/router/app modules |
| Idiomatic Python | Good | Uses `from __future__ import annotations`, `TYPE_CHECKING`, frozen sets |
| Missing: `if __name__ == "__main__"` block | Gap | No standalone runner, only usable via TestClient or import |

## 3. Example Coverage of Features

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

The dog_school example demonstrates core patterns (aggregates, events, validation, multi-tenancy, app factory) but omits several key framework features: projections, auth middleware, persistence, observability, and sagas. There is only one example application in the entire repository.

**Findings:**

| Feature | Demonstrated | Location |
|---------|-------------|----------|
| Aggregates | Yes | `domain.py:14-42` |
| Domain events | Yes | `domain.py:24,40` via `@event` decorator |
| Validation exceptions | Yes | `domain.py:37` |
| NotFound exceptions | Yes | `domain.py:45-49` |
| Multi-tenancy | Yes | `router.py:49` via `get_current_tenant_id()` |
| App factory auto-discovery | Yes | `app.py:51-54` |
| Pydantic DTOs | Yes | `router.py:27-40` |
| Auth (JWT/API key) | No | Excluded in `app.py:29-30` |
| Projections | No | Not demonstrated anywhere in examples |
| Event store persistence | No | Uses in-memory dict at `router.py:21` |
| Application services | No | No `Application[UUID]` usage |
| Observability | No | Excluded in `app.py:31` |
| Sagas/Integration | No | No cross-context example |
| Feature flags | No | Not demonstrated |
| Resource limits | No | Not demonstrated |

## 4. Integration Tests as Documentation

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The root-level integration tests are well-organized, readable, and effectively serve as usage documentation. Each test class has a docstring explaining what it proves. Tests are grouped by concern across four files.

**Findings:**

| Test File | Tests | Readability | Documentation Quality |
|-----------|-------|-------------|----------------------|
| `tests/test_integration_dog_school.py:1-70` | 6 tests | Excellent | Demonstrates domain and API lifecycle; docstrings on classes |
| `tests/test_integration_error_handling.py:1-74` | 5 tests | Excellent | Proves RFC 7807 compliance for 404, 422, content-type |
| `tests/test_integration_app_factory.py:1-42` | 4 tests | Excellent | Shows auto-discovery of health, routers, error handlers, CORS |
| `tests/test_integration_middleware.py:1-50` | 5 tests | Good | Shows request-id, correlation-id propagation, tenant context |
| `tests/conftest.py:1-48` | Fixtures | Good | Clear fixture names; `tenant_headers` documents required headers |

Strengths: descriptive test names, class docstrings, assertion of both status codes and response bodies. The `conftest.py` at `tests/conftest.py:16-24` documents which entry points need external services. One minor gap: no test demonstrates the `unhandled_exception_handler` behavior (500) at the integration level.

## 5. RFC 7807 Error Response Format

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The error handling module implements a thorough RFC 7807 Problem Details response format. The `ProblemDetail` Pydantic model at `packages/infra-fastapi/src/praecepta/infra/fastapi/error_handlers.py:47-99` defines all standard RFC 7807 fields (`type`, `title`, `status`, `detail`, `instance`) plus useful extensions (`error_code`, `context`, `correlation_id`). All responses use the `application/problem+json` media type (line 44).

**Findings:**

| RFC 7807 Field | Implemented | Location |
|----------------|-------------|----------|
| `type` | Yes | URI-style paths like `/errors/not-found` at `error_handlers.py:234` |
| `title` | Yes | Human-readable titles like "Resource Not Found" at `error_handlers.py:235` |
| `status` | Yes | HTTP status code at `error_handlers.py:236` |
| `detail` | Yes | Exception message at `error_handlers.py:237` |
| `instance` | Yes | Request path at `error_handlers.py:238` |
| `application/problem+json` | Yes | PROBLEM_MEDIA_TYPE constant at `error_handlers.py:44` |
| Extension: `error_code` | Yes | Machine-readable code at `error_handlers.py:87-91` |
| Extension: `context` | Yes | Structured debug info at `error_handlers.py:92-95` |
| Extension: `correlation_id` | Yes | For 500 errors at `error_handlers.py:96-99` |
| `exclude_none` serialization | Yes | Clean responses at `error_handlers.py:138` |

The implementation exceeds the PADR-103 reference spec, which described a simpler `to_dict()` pattern. The actual implementation uses Pydantic models with field descriptions and proper media type handling.

## 6. Domain Exception Context

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Domain exceptions carry rich, structured context suitable for debugging. Every exception subclass includes typed attributes and a `context` dictionary with relevant identifiers.

**Findings:**

| Exception | Context Fields | Reference |
|-----------|---------------|-----------|
| `DomainError` | `message`, `context` dict, `error_code` | `exceptions.py:50-68` |
| `NotFoundError` | `resource_type`, `resource_id`, `**extra_context` | `exceptions.py:95-116` |
| `ValidationError` | `field`, `reason`, `**extra_context` | `exceptions.py:137-159` |
| `ConflictError` | `reason`, `**context` (e.g., `expected_version`, `actual_version`) | `exceptions.py:183-198` |
| `InvalidStateTransitionError` | Inherits `ConflictError` context, custom `error_code` | `exceptions.py:218-225` |
| `FeatureDisabledError` | `feature_key`, `tenant_id` | `exceptions.py:245-256` |
| `AuthenticationError` | `auth_error` (RFC 6750), custom `error_code`, `context` | `exceptions.py:276-293` |
| `AuthorizationError` | Inherits base context | `exceptions.py:296-309` |
| `ResourceLimitExceededError` | `resource`, `limit`, `current`, `**extra_context` | `exceptions.py:330-355` |

Notable: `DomainError.__str__` at `exceptions.py:64-69` includes context in the string representation (`"Failed (key=value)"`), making log messages informative. `DomainError.__repr__` at `exceptions.py:71-73` provides full debugging output. All exception constructors have comprehensive docstrings with `Args:` sections.

## 7. Validation Error Messages

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Validation error messages are user-friendly. Domain `ValidationError` at `exceptions.py:137-159` includes both field path and human-readable reason. Pydantic `RequestValidationError` at `error_handlers.py:441-477` is reformatted with `loc`, `msg`, and `type` fields.

**Findings:**

| Validation Type | Format | Reference |
|-----------------|--------|-----------|
| Domain `ValidationError` | `"Validation failed for 'field': reason"` | `exceptions.py:153` |
| Field path support | Dot-notation documented in docstring: `"metadata.source_url"` | `exceptions.py:147-148` |
| Pydantic `RequestValidationError` | `{"errors": [{"loc": [...], "msg": "...", "type": "..."}]}` | `error_handlers.py:459-466` |
| Context includes field and reason | Yes, in `context` dict | `exceptions.py:154-158` |

Minor gap: the Dog School example only demonstrates a single validation case (`domain.py:37`). There is no example of multi-field validation, nested field paths, or batch validation aggregation. The `ValidationError` constructor only supports a single field+reason pair -- it does not support multiple validation errors in a single response (unlike the PADR-103 spec which envisioned `ErrorDetail` lists).

## 8. Error Handler Coverage

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All domain exceptions are mapped to appropriate HTTP status codes. The `register_exception_handlers` function at `error_handlers.py:535-612` registers 10 handlers covering the full exception hierarchy plus Pydantic validation and a catch-all.

**Findings:**

| Exception | HTTP Status | Handler | Reference |
|-----------|-------------|---------|-----------|
| `AuthenticationError` | 401 | `authentication_error_handler` | `error_handlers.py:359-385` |
| `AuthorizationError` | 403 | `authorization_error_handler` | `error_handlers.py:388-410` |
| `NotFoundError` | 404 | `not_found_handler` | `error_handlers.py:223-242` |
| `ValidationError` | 422 | `validation_error_handler` | `error_handlers.py:245-267` |
| `ConflictError` | 409 | `conflict_error_handler` | `error_handlers.py:270-292` |
| `FeatureDisabledError` | 403 | `feature_disabled_handler` | `error_handlers.py:295-320` |
| `ResourceLimitExceededError` | 429 | `resource_limit_handler` | `error_handlers.py:323-356` |
| `DomainError` (base fallback) | 400 | `domain_error_handler` | `error_handlers.py:413-438` |
| `RequestValidationError` (Pydantic) | 422 | `request_validation_handler` | `error_handlers.py:441-477` |
| `Exception` (catch-all) | 500 | `unhandled_exception_handler` | `error_handlers.py:480-532` |

Additional protocol compliance: `AuthenticationError` handler includes `WWW-Authenticate` header per RFC 6750 (`error_handlers.py:384`). `ResourceLimitExceededError` handler includes `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `Retry-After` headers (`error_handlers.py:353-355`). `InvalidStateTransitionError` is a subclass of `ConflictError` and is caught by the 409 handler automatically.

## 9. Stack Trace Safety

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Internal stack traces are thoroughly protected from API consumers. The `unhandled_exception_handler` at `error_handlers.py:480-532` implements a debug/production mode toggle.

**Findings:**

| Protection | Implementation | Reference |
|------------|---------------|-----------|
| Production mode (default) | Returns generic message: `"An internal error occurred. Please contact support with the correlation ID."` | `error_handlers.py:519` |
| Debug mode (`DEBUG=true`) | Shows exception type and message only (no traceback) | `error_handlers.py:516` |
| Full exception logged server-side | `logger.exception()` with correlation ID | `error_handlers.py:502-510` |
| Correlation ID in response | For support requests | `error_handlers.py:530` |
| Sensitive data sanitization | Strips passwords, tokens, API keys, connection strings from `context` dicts | `error_handlers.py:102-124, 161-219` |
| Sensitive key filtering | Blocks `password`, `secret`, `token`, `api_key`, `apikey`, `credential` | `error_handlers.py:189-192` |
| Connection string redaction | Regex for `postgresql://`, `password=`, `secret=`, `token=`, `api_key=` | `error_handlers.py:103-124` |
| Test coverage | Unit tests verify production mode hides "kaboom" and debug mode shows it | `test_error_handlers.py:353-386` |

## 10. Error Response Consistency

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

Error responses are structurally consistent across all endpoints due to the centralized `ProblemDetail` model and `_create_problem_response` helper. All error responses share the same shape and media type.

**Findings:**

| Consistency Aspect | Status | Detail |
|--------------------|--------|--------|
| Same model for all errors | Yes | `ProblemDetail` at `error_handlers.py:47-99` |
| Same content-type | Yes | `application/problem+json` via `_create_problem_response` at `error_handlers.py:127-140` |
| Same `exclude_none` serialization | Yes | `error_handlers.py:138` |
| `instance` path always set | Yes | All handlers use `str(request.url.path)` |
| `error_code` always present | Yes | Every exception has class-level `error_code` |
| Integration tests verify consistency | Partial | `test_integration_error_handling.py:62-74` checks content-type for 404 and 422 |

One inconsistency identified -- **documentation vs. implementation mismatch on status codes:**

| Exception | Docs Say (`add-api-endpoint.md:65-70`) | Actual Handler |
|-----------|--------|--------|
| `ValidationError` | 400 Bad Request | 422 Unprocessable Entity (`error_handlers.py:259`) |

The guide at `docs/docs/guides/add-api-endpoint.md:66` states `ValidationError` maps to `400 Bad Request`, but the actual handler at `error_handlers.py:259` returns `422`. The PADR-103 reference at `_kb/decisions/patterns/PADR-103-error-handling.md:282` also says 400. This documentation inconsistency could confuse developers building against the guides.

Additionally, the guide at `docs/docs/guides/add-api-endpoint.md:81` uses `raise NotFoundError(f"Order {order_id} not found")` which passes a single string argument, but the actual `NotFoundError.__init__` at `exceptions.py:95-99` requires two arguments `(resource_type, resource_id)`. This code in the guide would raise a `TypeError` at runtime.

## 11. Example README/Instructions

**Rating: 1/5 -- Not Implemented**
**Severity:** High | **Confidence:** High

The `examples/dog_school/` directory has no README, no setup instructions, no `__main__.py`, and no standalone run command. The only way to discover how to use the example is to read the source code or the integration tests.

**Findings:**

| Expected Artifact | Present | Location |
|-------------------|---------|----------|
| `README.md` | No | `examples/dog_school/` has no README |
| Setup instructions | No | No instructions for installing dependencies |
| Run command (`uvicorn` / `python -m`) | No | No `__main__.py` or documented command |
| `requirements.txt` / deps | No | Dependencies implicit from workspace |
| Docker/compose for external services | No | N/A (in-memory example) |
| Quick-start steps | No | Only the `quickstart.md` guide exists at `docs/docs/getting-started/quickstart.md:1-100` but it describes a separate `my-app` project, not the dog_school example |
| Inline usage comment | Partial | `app.py:7-11` has a `Usage::` docstring block |

The `__init__.py` at `examples/dog_school/__init__.py:1-11` has a module docstring that names the modules, and `app.py:7-11` has a `Usage::` block showing the import, but neither explains how to actually start the server or run the tests.

## 12. Error Documentation

**Rating: 2/5 -- Initial**
**Severity:** High | **Confidence:** High

Error documentation exists in fragmented form across the codebase but there is no dedicated error reference guide. The `add-api-endpoint.md` guide includes an incomplete and partially incorrect error mapping table. There are no documented resolution steps for common errors.

**Findings:**

| Documentation Location | Content | Quality |
|------------------------|---------|---------|
| `docs/docs/guides/add-api-endpoint.md:62-93` | Status code mapping table + JSON example | Incorrect: shows only 5 of 10 handlers; `ValidationError` wrongly listed as 400 |
| `exceptions.py:1-355` | Docstrings with examples for each exception | Good: includes `Example:` blocks, `Args:` documentation |
| `error_handlers.py:1-12` | Module docstring | Brief: describes purpose, usage import |
| `error_handlers.py:535-563` | `register_exception_handlers` docstring | Good: lists all 10 handlers with status codes |
| `_kb/decisions/patterns/PADR-103-error-handling.md` | Architecture decision record | Draft status; describes a different (older) exception hierarchy |
| API reference docs | `docs/docs/reference/foundation-domain.md` and `infra-fastapi.md` | Auto-generated stubs only (`:::` directives) |

**Missing documentation:**

- No dedicated "Error Handling Guide" in `docs/docs/guides/`
- No troubleshooting section for common errors (missing tenant header, invalid UUID format, etc.)
- No documentation of the `ProblemDetail` response schema for API consumers
- No OpenAPI example responses documented on endpoints
- PADR-103 decision record is stale -- describes `ErrorDetail`/`BaseError` hierarchy that does not match the implemented `DomainError` hierarchy
- The `ValidationError` status code discrepancy between docs (400) and implementation (422) is not documented anywhere

---

## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | Dog School Example Completeness | 4/5 | Medium |
| 2 | Example Code Quality | 4/5 | Low |
| 3 | Example Coverage of Features | 3/5 | Medium |
| 4 | Integration Tests as Documentation | 4/5 | Low |
| 5 | RFC 7807 Error Response Format | 5/5 | Info |
| 6 | Domain Exception Context | 5/5 | Info |
| 7 | Validation Error Messages | 4/5 | Low |
| 8 | Error Handler Coverage | 5/5 | Info |
| 9 | Stack Trace Safety | 5/5 | Info |
| 10 | Error Response Consistency | 4/5 | Medium |
| 11 | Example README/Instructions | 1/5 | High |
| 12 | Error Documentation | 2/5 | High |

**Overall average: 3.8/5**

**Top findings requiring action:**

1. **Example README/Instructions (1/5):** The dog_school example has no README, no standalone run instructions, and no `__main__.py`. This is the most critical gap for developer onboarding.
2. **Error Documentation (2/5):** No dedicated error handling guide exists. The `add-api-endpoint.md` guide contains an incorrect `ValidationError` status code mapping (says 400, actual is 422) at `docs/docs/guides/add-api-endpoint.md:66`, and an incorrect `NotFoundError` constructor call at `docs/docs/guides/add-api-endpoint.md:81` that would fail at runtime. PADR-103 is stale and does not reflect the implemented hierarchy.
3. **Example Feature Coverage (3/5):** Only one example exists (dog_school), and it does not demonstrate projections, auth, persistence, application services, or feature flags -- all of which are core framework capabilities.
