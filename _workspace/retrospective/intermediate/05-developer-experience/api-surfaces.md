# API Surfaces & Type Annotations -- Developer Experience

**Collector ID:** 5A
**Dimension:** Developer Experience
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. `__all__` Export Completeness

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

Nearly all leaf `__init__.py` files define `__all__`, and the exports match the imports. Two notable gaps exist.

**Findings:**

| File | Status | Detail |
|------|--------|--------|
| `packages/foundation-domain/src/praecepta/foundation/domain/__init__.py:54` | Complete | 39 symbols exported, all match imports on lines 8-52 |
| `packages/foundation-domain/src/praecepta/foundation/domain/ports/__init__.py:10` | Complete | 2 symbols exported |
| `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:20` | Complete | 9 symbols exported |
| `packages/foundation-application/src/praecepta/foundation/application/__init__.py:45` | Complete | 23 symbols exported |
| `packages/infra-fastapi/src/praecepta/infra/fastapi/__init__.py:26` | Complete | 14 symbols exported |
| `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/__init__.py:11` | Complete | 9 symbols exported |
| `packages/infra-auth/src/praecepta/infra/auth/__init__.py:38` | Complete | 16 symbols exported |
| `packages/infra-persistence/src/praecepta/infra/persistence/__init__.py:18` | Complete | 10 symbols exported |
| `packages/infra-observability/src/praecepta/infra/observability/__init__.py:43` | Complete | 8 symbols exported |
| `packages/infra-taskiq/src/praecepta/infra/taskiq/__init__.py:5` | Complete | 3 symbols exported |
| `packages/domain-tenancy/src/praecepta/domain/tenancy/__init__.py:6` | Complete | 2 symbols exported |
| `packages/domain-identity/src/praecepta/domain/identity/__init__.py:8` | Complete | 4 symbols exported |
| `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` | **Missing `__all__`** | Only a docstring; no exports. Stub package, but should still define `__all__ = []` for completeness |
| `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` | **Missing `__all__`** | Only a docstring `"""Authentication middleware subpackage."""`; does not re-export `JWTAuthMiddleware` or `APIKeyAuthMiddleware` |

Subpackage `__init__.py` files that DO define `__all__`:
- `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/__init__.py:13` -- 4 symbols
- `packages/infra-fastapi/src/praecepta/infra/fastapi/dependencies/__init__.py:10` -- 2 symbols
- `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projections/__init__.py:12` -- 4 symbols
- `packages/domain-identity/src/praecepta/domain/identity/infrastructure/__init__.py:18` -- 5 symbols
- `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/__init__.py:10` -- 2 symbols
- `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/__init__.py:15` -- 5 symbols
- `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/projections/__init__.py:10` -- 2 symbols


## 2. Import Ergonomics

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All key types are importable from the top-level package namespace, enabling 1-level imports for common use cases. The `__init__.py` re-export strategy is thorough.

**Findings:**

| Import Pattern | Example | Works? |
|----------------|---------|--------|
| Foundation domain types | `from praecepta.foundation.domain import BaseAggregate, BaseEvent, TenantId` | Yes (`__init__.py:14,26,38`) |
| All exceptions | `from praecepta.foundation.domain import NotFoundError, ValidationError` | Yes (`__init__.py:27-37`) |
| All value objects | `from praecepta.foundation.domain import TenantSlug, Email, AgentStatus` | Yes (`__init__.py:8-52`) |
| Port interfaces | `from praecepta.foundation.domain import LLMServicePort, APIKeyGeneratorPort` | Yes (`__init__.py:40`) |
| Application context | `from praecepta.foundation.application import get_current_tenant_id, RequestContext` | Yes (`__init__.py:4-17`) |
| Contributions | `from praecepta.foundation.application import MiddlewareContribution, LifespanContribution` | Yes (`__init__.py:18-22`) |
| App factory | `from praecepta.infra.fastapi import create_app` | Yes (`__init__.py:13`) |
| Auth components | `from praecepta.infra.auth import JWKSProvider, JWTAuthMiddleware` | Yes (`__init__.py:8-24`) |
| Domain aggregates | `from praecepta.domain.tenancy import Tenant, TenantApplication` | Yes (`__init__.py:3-4`) |
| Projections | `from praecepta.infra.eventsourcing import BaseProjection, ProjectionPoller` | Yes (`__init__.py:7-8`) |

The design follows a clear pattern: each leaf `__init__.py` imports and re-exports all public symbols from its internal modules, so consumers never need to reach into implementation modules.


## 3. Type Annotation Completeness

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

All public functions and methods have full type annotations for parameters and return types. The codebase uses `from __future__ import annotations` consistently for PEP 604 union syntax. The main gap is intentional use of `Any` in several places where more specific types could be provided.

**Findings:**

| Location | Issue | Severity |
|----------|-------|----------|
| `packages/foundation-application/src/praecepta/foundation/application/contributions.py:40` | `handler: Any  # Callable[[Request, Exception], Awaitable[Response]]` | Medium -- comment documents the type but type checker cannot verify it |
| `packages/foundation-application/src/praecepta/foundation/application/contributions.py:52` | `hook: Any  # Callable[[Any], AsyncContextManager[None]]` | Medium -- same pattern |
| `packages/foundation-application/src/praecepta/foundation/application/contributions.py:25` | `middleware_class: type[Any]` | Low -- reasonable since ASGI middleware types vary |
| `packages/foundation-application/src/praecepta/foundation/application/issue_api_key.py:28` | `def repository(self) -> Any: ...` in `EventSourcedApplication` Protocol | Medium -- returns untyped repository |
| `packages/foundation-application/src/praecepta/foundation/application/issue_api_key.py:30` | `def save(self, aggregate: Any) -> None: ...` | Medium -- aggregate parameter untyped |
| `packages/foundation-application/src/praecepta/foundation/application/issue_api_key.py:82` | `agent: Any = self._app.repository.get(cmd.agent_id)` | Medium -- cascading from untyped repository |
| `packages/foundation-application/src/praecepta/foundation/application/rotate_api_key.py:19-29` | Duplicate `EventSourcedApplication` Protocol with same `Any` issues | Medium -- also a DRY violation |
| `packages/foundation-application/src/praecepta/foundation/application/discovery.py:29` | `value: Any` in `DiscoveredContribution` | Low -- inherent to entry point loading |
| `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:58` | `self._client: Any = None` | Medium -- could be `redis.asyncio.Redis | None` |
| `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projections/runner.py:211` | `exc_tb: Any` | Low -- standard `__exit__` pattern; could use `TracebackType | None` |

Positive observations:
- All public function return types are annotated
- `TYPE_CHECKING` guards used correctly to avoid circular imports (`context.py:36-40`, `identifiers.py:19-21`)
- Modern union syntax `X | None` used consistently instead of `Optional[X]`
- No functions found with completely missing return type annotations (only docstring examples in `aggregates.py` lines 14, 63)
- `mypy --strict` configuration enforces annotations at the CI level


## 4. `py.typed` Markers

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

All 11 packages have PEP 561 `py.typed` marker files in the correct location (the leaf package directory alongside `__init__.py`).

**Findings:**

| Package | `py.typed` Location | Present? |
|---------|---------------------|----------|
| praecepta-foundation-domain | `packages/foundation-domain/src/praecepta/foundation/domain/py.typed` | Yes |
| praecepta-foundation-application | `packages/foundation-application/src/praecepta/foundation/application/py.typed` | Yes |
| praecepta-infra-fastapi | `packages/infra-fastapi/src/praecepta/infra/fastapi/py.typed` | Yes |
| praecepta-infra-eventsourcing | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/py.typed` | Yes |
| praecepta-infra-auth | `packages/infra-auth/src/praecepta/infra/auth/py.typed` | Yes |
| praecepta-infra-persistence | `packages/infra-persistence/src/praecepta/infra/persistence/py.typed` | Yes |
| praecepta-infra-observability | `packages/infra-observability/src/praecepta/infra/observability/py.typed` | Yes |
| praecepta-infra-taskiq | `packages/infra-taskiq/src/praecepta/infra/taskiq/py.typed` | Yes |
| praecepta-domain-tenancy | `packages/domain-tenancy/src/praecepta/domain/tenancy/py.typed` | Yes |
| praecepta-domain-identity | `packages/domain-identity/src/praecepta/domain/identity/py.typed` | Yes |
| praecepta-integration-tenancy-identity | `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/py.typed` | Yes |

All markers are in the correct PEP 561 location (inside the leaf package directory, not at package root). This ensures downstream consumers using `mypy` will treat these packages as typed.


## 5. Protocol Usage

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Port interfaces consistently use `typing.Protocol` with `@runtime_checkable` for structural subtyping. All domain-level port definitions follow this pattern. Two minor issues exist.

**Findings:**

| Protocol | File | `@runtime_checkable` | Docstring |
|----------|------|---------------------|-----------|
| `LLMServicePort` | `packages/foundation-domain/src/praecepta/foundation/domain/ports/llm_service.py:23` | Yes | Excellent |
| `APIKeyGeneratorPort` | `packages/foundation-domain/src/praecepta/foundation/domain/ports/api_key_generator.py:20` | Yes | Excellent |
| `ConfigRepository` | `packages/foundation-application/src/praecepta/foundation/application/config_service.py:22` | No | Adequate |
| `ConfigCache` | `packages/foundation-application/src/praecepta/foundation/application/config_service.py:48` | No | Adequate |
| `EventSourcedApplication` | `packages/foundation-application/src/praecepta/foundation/application/issue_api_key.py:20` | No | Adequate |
| `EventSourcedApplication` (duplicate) | `packages/foundation-application/src/praecepta/foundation/application/rotate_api_key.py:19` | No | Adequate |
| `FeatureChecker` | `packages/infra-fastapi/src/praecepta/infra/fastapi/dependencies/feature_flags.py:31` | No | Good |

Issues:
- `EventSourcedApplication` Protocol is duplicated across `issue_api_key.py:20` and `rotate_api_key.py:19` -- should be defined once and imported. This is a DRY violation.
- The foundation-level ports (`LLMServicePort`, `APIKeyGeneratorPort`) are `@runtime_checkable`, but application-level protocols (`ConfigRepository`, `ConfigCache`, `EventSourcedApplication`) are not. The pattern should be consistent -- either all or none should be `@runtime_checkable`.
- `ConfigRepository` and `ConfigCache` protocols are not re-exported from `foundation.application.__init__.py`, making them harder to discover.


## 6. Generic Type Parameters

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Generic types are properly parameterized throughout the codebase. The key generic pattern is `Application[UUID]` from the eventsourcing library, and all usages correctly specify the `UUID` type parameter.

**Findings:**

| Usage | File | Correct? |
|-------|------|----------|
| `class TenantApplication(Application[UUID])` | `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant_app.py:17` | Yes |
| `class UserApplication(Application[UUID])` | `packages/domain-identity/src/praecepta/domain/identity/user_app.py:17` | Yes |
| `class AgentApplication(Application[UUID])` | `packages/domain-identity/src/praecepta/domain/identity/agent_app.py:17` | Yes |
| `class BaseProjection(ProcessApplication[UUID])` | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projections/base.py:58` | Yes |
| `processing_event: ProcessingEvent[UUID]` | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projections/base.py:110` | Yes |
| `RunnerType = Runner[UUID]` | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projections/runner.py:51` | Yes |
| `T = TypeVar("T", bound=BaseModel)` | `packages/foundation-domain/src/praecepta/foundation/domain/ports/llm_service.py:19` | Yes -- proper bound |
| `response_type: type[T]` | `packages/foundation-domain/src/praecepta/foundation/domain/ports/llm_service.py:65` | Yes -- uses bounded TypeVar |
| `ConfigValue = Annotated[..., Field(discriminator="type")]` | `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:100` | Yes -- Pydantic discriminated union |

The `TypeVar("T", bound=BaseModel)` in `llm_service.py:19` is correctly bounded so that `complete_structured()` preserves the concrete return type. The `Annotated` discriminated union for `ConfigValue` is a well-chosen pattern for type-safe configuration values.


## 7. Docstring Coverage

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

Docstring coverage is exceptional. Every public class, method, and function has a docstring. Module-level docstrings are present on all source files. Docstrings follow Google-style conventions with `Args:`, `Returns:`, `Raises:`, and `Example:` sections consistently.

**Findings:**

| Category | Coverage | Quality |
|----------|----------|---------|
| Module docstrings | 100% of source files | Informative -- describe purpose, not just name (e.g., `events.py:1-52` includes full schema evolution guide) |
| Class docstrings | 100% of public classes | Thorough -- include Attributes, Examples, and See Also sections (e.g., `BaseAggregate` at `aggregates.py:27-101`) |
| Method docstrings | 100% of public methods | Complete -- Args/Returns/Raises documented (e.g., `BaseEvent.to_dict()` at `events.py:216-256`) |
| Protocol docstrings | 100% of protocol methods | All methods have Args/Returns documented (e.g., `LLMServicePort.complete()` at `llm_service.py:38-60`) |
| Exception docstrings | 100% of exception classes | Include HTTP status mapping and Examples (e.g., `NotFoundError` at `exceptions.py:76-91`) |

Standout examples:
- `events.py:1-52` -- Module docstring documents event schema evolution strategy with examples for backward-compatible and breaking changes
- `aggregates.py:27-101` -- `BaseAggregate` docstring includes usage pattern, command pattern, and references to related classes
- `projections/base.py:1-42` -- Module docstring includes full projection implementation example with idempotency requirement callout
- `config_service.py:72-104` -- `_evaluate_percentage_flag` documents the hashing algorithm step by step with mathematical properties


## 8. API Consistency

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The codebase follows consistent naming patterns across packages. The command-method pattern (`request_*` for aggregate commands) and the handler pattern (Command + Handler classes) are applied uniformly. One inconsistency exists.

**Findings:**

| Pattern | Where Used | Consistent? |
|---------|-----------|-------------|
| `request_*` for aggregate commands | `Tenant` (`request_activate`, `request_suspend`, `request_reactivate`, `request_decommission`, `request_update_config`, `request_update_metadata`), `Agent` (`request_suspend`, `request_reactivate`, `request_issue_api_key`, `request_rotate_api_key`), `User` (`request_update_display_name`, `request_update_preferences`) | Yes -- all 12 command methods follow the pattern |
| `_apply_*` for event mutators | All 3 aggregates | Yes -- all private `@event` decorators use `_apply_` prefix |
| `*Application` for app services | `TenantApplication`, `UserApplication`, `AgentApplication` | Yes |
| `*Command` / `*Handler` | `IssueAPIKeyCommand`/`IssueAPIKeyHandler`, `RotateAPIKeyCommand`/`RotateAPIKeyHandler` | Yes |
| `*Settings` for config | `AppSettings`, `CORSSettings`, `AuthSettings`, `EventSourcingSettings`, `ProjectionPollingSettings`, `DatabaseSettings`, `RedisSettings`, `LoggingSettings`, `TracingSettings` | Yes |
| `*Contribution` for discovery | `MiddlewareContribution`, `ErrorHandlerContribution`, `LifespanContribution` | Yes |
| `*Projection` for read models | `TenantListProjection`, `TenantConfigProjection`, `UserProfileProjection`, `AgentAPIKeyProjection` | Yes |
| `get_*` for retrieval functions | `get_current_tenant_id`, `get_current_user_id`, `get_current_principal`, `get_event_store`, `get_auth_settings`, `get_db_session`, `get_logger`, `get_request_id` | Yes |

Minor inconsistency:
- `User.request_update_display_name` vs `User.request_update_preferences` -- the `display_name` method validates via `DisplayName` value object (`user.py:81`) while `preferences` method does no validation (`user.py:84-90`). This is a semantic inconsistency (not naming), but the asymmetry in validation is worth noting.
- `record_data_deleted` on `Tenant` (`tenant.py:299`) breaks the `request_*` naming convention for command methods. While it is intentionally an audit-only event (no state change), it could be confusing since other `@event`-producing methods all use the `request_*` prefix.


## 9. Return Type Clarity

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

Return types are explicit and use appropriate concrete types. Two patterns are noteworthy.

**Findings:**

| Pattern | Examples | Assessment |
|---------|----------|------------|
| Dataclass return types | `ResourceLimitResult` (`resource_limits.py:25`), `PolicyResolution` (`policy_binding.py:30`), `RotateAPIKeyResult` (`rotate_api_key.py:40`), `RequestContext` (`context.py:43`) | Excellent -- named types with clear attributes |
| Pydantic model returns | `ProblemDetail` (`error_handlers.py:47`) | Excellent -- RFC 7807 compliant model |
| Tuple returns | `IssueAPIKeyHandler.handle() -> tuple[str, str]` (`issue_api_key.py:62`) | Adequate -- documented as `(key_id, full_plaintext_key)` but a named tuple or dataclass would be clearer |
| `dict[str, Any]` returns | `TenantConfigService.get_config() -> dict[str, Any] | None` (`config_service.py:149`), `TenantConfigService.get_all_config() -> list[dict[str, Any]]` (`config_service.py:198`), `BaseEvent.to_dict() -> dict[str, Any]` (`events.py:216`) | Medium concern -- these return dicts with known structure (`key`, `value`, `source` fields) that could be a typed dataclass or TypedDict |
| `Optional` types | All `Optional` types expressed as `X | None` throughout | Excellent -- modern syntax, always explicit |

Specific issues:
- `config_service.py:149` -- `get_config()` returns `dict[str, Any] | None` with keys `key`, `value`, `source`. This is used by `is_feature_enabled()` (`config_service.py:262-268`) and `resolve_limit()` (`config_service.py:324-326`) with direct string-key access. A `ConfigResolution` TypedDict or dataclass would improve type safety.
- `config_service.py:198` -- `get_all_config()` returns `list[dict[str, Any]]` -- same pattern.
- `issue_api_key.py:62` -- `handle() -> tuple[str, str]` documented as `(key_id, full_plaintext_key)` but compared to `RotateAPIKeyHandler.handle() -> RotateAPIKeyResult` which returns a named dataclass with the same information. Inconsistency between the two handlers.


## 10. Error Type Hierarchy

**Rating: 5/5 -- Optimizing**
**Severity:** Info | **Confidence:** High

The exception hierarchy is well-designed with clear HTTP status code mappings, structured context for debugging, and machine-readable error codes. Users can catch at any granularity.

**Findings:**

Exception tree (from `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py`):

```
Exception
  DomainError (400)                          :33
    NotFoundError (404)                       :76
    ValidationError (422)                     :119
    ConflictError (409)                       :162
      InvalidStateTransitionError (409)       :201
    FeatureDisabledError (403)                :228
    AuthenticationError (401)                 :259
    AuthorizationError (403)                  :296
    ResourceLimitExceededError (429)          :312
RuntimeError
  NoRequestContextError                       context.py:62
```

Design strengths:
- Every exception carries `error_code` (machine-readable) and `context` (structured debugging data)
- `InvalidStateTransitionError` extends `ConflictError` -- catch broad or narrow
- Each exception class documents its HTTP status code mapping in the docstring
- RFC 7807 error handler mapping at `error_handlers.py:535-612` maps each exception type to a specific handler
- The hierarchy supports 5 levels of catch granularity:
  1. `except Exception` -- everything
  2. `except DomainError` -- all domain errors
  3. `except ConflictError` -- conflicts and state transitions
  4. `except InvalidStateTransitionError` -- just state machine violations
  5. Individual types (`NotFoundError`, `ValidationError`, etc.)

Additional domain-specific exception (`TokenExchangeError` at `packages/infra-auth/src/praecepta/infra/auth/oidc_client.py`) is also available for OAuth error handling, exported via `praecepta.infra.auth.__init__.py:21`.


## 11. Overload/Union Clarity

**Rating: 3/5 -- Defined**
**Severity:** Low | **Confidence:** High

No `@overload` decorators are used anywhere in the codebase. The codebase uses modern `X | Y` union syntax consistently. There are a few places where `@overload` could improve the developer experience, but the current approach is functional.

**Findings:**

| Pattern | File | Assessment |
|---------|------|------------|
| `config_value: dict[str, Any] | BaseModel` | `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:237` | Could benefit from `@overload` to narrow the return type based on input type, though the method always returns `None` |
| `resource_id: UUID | str` | `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:98` | Acceptable -- both are converted to `str` internally |
| `ConfigValue` discriminated union | `packages/foundation-domain/src/praecepta/foundation/domain/config_value_objects.py:100-108` | Well-documented `Annotated` union with Pydantic discriminator |
| `Token[RequestContext | None]` return | `packages/foundation-application/src/praecepta/foundation/application/context.py:127` | Clear parametric type |
| `Callable[[Request], FeatureChecker] | None` | `packages/infra-fastapi/src/praecepta/infra/fastapi/dependencies/feature_flags.py:65` | Clean optional callable |

Places where `@overload` would help:
- `EventStoreFactory` or `ProjectionRunner.get()` could use `@overload` to narrow the return type based on the `application_class` parameter (currently returns `Any`)
- `TenantConfigService.get_config()` returns `dict[str, Any] | None` -- if it returned different TypedDict types based on source, `@overload` would help

Overall, the absence of `@overload` is not a deficiency given the project's current scope. The codebase avoids complex multi-signature methods, keeping the API surfaces simple.


## 12. Subpackage `__init__.py` Exports

**Rating: 4/5 -- Managed**
**Severity:** Medium | **Confidence:** High

Most subpackages properly re-export their contents. Two gaps exist.

**Findings:**

| Subpackage | File | Exports | Status |
|------------|------|---------|--------|
| `infra.fastapi.middleware` | `packages/infra-fastapi/src/praecepta/infra/fastapi/middleware/__init__.py:1-18` | `RequestContextMiddleware`, `RequestIdMiddleware`, `TenantStateMiddleware`, `get_request_id` | Complete |
| `infra.fastapi.dependencies` | `packages/infra-fastapi/src/praecepta/infra/fastapi/dependencies/__init__.py:1-13` | `require_feature`, `check_resource_limit` | Complete |
| `infra.eventsourcing.projections` | `packages/infra-eventsourcing/src/praecepta/infra/eventsourcing/projections/__init__.py:1-17` | `BaseProjection`, `ProjectionPoller`, `ProjectionRebuilder`, `ProjectionRunner` | Complete |
| `domain.identity.infrastructure` | `packages/domain-identity/src/praecepta/domain/identity/infrastructure/__init__.py:1-25` | 5 symbols: repositories, registry, provisioning service | Complete |
| `domain.identity.infrastructure.projections` | `packages/domain-identity/src/praecepta/domain/identity/infrastructure/projections/__init__.py:1-13` | `AgentAPIKeyProjection`, `UserProfileProjection` | Complete |
| `domain.tenancy.infrastructure` | `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/__init__.py:1-21` | 5 symbols: repositories, deletion service | Complete |
| `domain.tenancy.infrastructure.projections` | `packages/domain-tenancy/src/praecepta/domain/tenancy/infrastructure/projections/__init__.py:1-12` | `TenantConfigProjection`, `TenantListProjection` | Complete |
| `infra.auth.middleware` | `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` | **None** | **Gap** -- Only has a docstring. Does not re-export `JWTAuthMiddleware` or `APIKeyAuthMiddleware`. Users must import from deep modules: `from praecepta.infra.auth.middleware.jwt_auth import JWTAuthMiddleware` |
| `foundation.domain.ports` | `packages/foundation-domain/src/praecepta/foundation/domain/ports/__init__.py:1-10` | `APIKeyGeneratorPort`, `LLMServicePort` | Complete |

The `infra.auth.middleware.__init__.py` gap is the most significant. The parent `__init__.py` (`packages/infra-auth/src/praecepta/infra/auth/__init__.py:16-17`) does re-export `APIKeyAuthMiddleware` and `JWTAuthMiddleware` at the top package level, so the practical impact is mitigated. However, the empty middleware subpackage `__init__.py` is inconsistent with the pattern used by `infra.fastapi.middleware`, which properly re-exports all its middleware classes.


---

## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | `__all__` Export Completeness | 4/5 | Medium |
| 2 | Import Ergonomics | 5/5 | Info |
| 3 | Type Annotation Completeness | 4/5 | Medium |
| 4 | `py.typed` Markers | 5/5 | Info |
| 5 | Protocol Usage | 4/5 | Low |
| 6 | Generic Type Parameters | 5/5 | Info |
| 7 | Docstring Coverage | 5/5 | Info |
| 8 | API Consistency | 4/5 | Low |
| 9 | Return Type Clarity | 4/5 | Medium |
| 10 | Error Type Hierarchy | 5/5 | Info |
| 11 | Overload/Union Clarity | 3/5 | Low |
| 12 | Subpackage `__init__.py` Exports | 4/5 | Medium |

**Overall weighted average: 4.3/5**

**Top strengths:**
- Exceptional docstring coverage with examples, schema evolution guides, and algorithm documentation
- All 11 packages have correct `py.typed` markers
- Well-designed exception hierarchy with HTTP status code mappings and structured context
- 1-level imports work for all key types across the entire monorepo
- Generic type parameters consistently applied with proper bounds

**Top improvement opportunities:**
1. Add typed return value (TypedDict or dataclass) for `TenantConfigService.get_config()` / `get_all_config()` instead of `dict[str, Any]` (item 9)
2. Eliminate duplicate `EventSourcedApplication` Protocol between `issue_api_key.py` and `rotate_api_key.py` (item 5)
3. Replace `Any` types on `MiddlewareContribution.middleware_class`, `ErrorHandlerContribution.handler`, and `LifespanContribution.hook` with proper `Callable` type aliases (item 3)
4. Add re-exports to `infra.auth.middleware.__init__.py` to match the pattern used by `infra.fastapi.middleware.__init__.py` (item 12)
5. Add `__all__ = []` to the stub `integration.tenancy_identity.__init__.py` (item 1)
