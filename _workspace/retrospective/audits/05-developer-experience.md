# Dimension 5: Developer Experience

**RAG Status:** RED
**Average Maturity:** 3.7/5
**Date:** 2026-02-18

## Executive Summary

The Praecepta framework delivers a strong API surface and error-handling experience. Type annotations are thorough (enforced by mypy strict mode), every public class and method carries a quality docstring, all 11 packages ship PEP 561 `py.typed` markers, and the import ergonomics are excellent -- consumers can import all key symbols from top-level package namespaces without reaching into internal modules. The RFC 7807 error response implementation, exception hierarchy with structured context, and stack-trace safety measures are all exemplary. These strengths indicate genuine care for downstream developer experience at the code level.

However, the developer experience deteriorates significantly once a newcomer moves beyond reading source code to seeking documentation, examples, and onboarding materials. There is no changelog despite the project advancing from 0.1.0 to 0.3.0, no CONTRIBUTING.md, and no dedicated error-handling guide. The sole example application (dog_school) lacks a README and standalone run instructions. Guides contain factual errors -- notably an incorrect `ValidationError` status-code mapping (docs say 400, code returns 422) and a `NotFoundError` constructor call that would raise a `TypeError` at runtime. The Development Constitution contains an unresolved template placeholder and contradicts an accepted PADR.

The overall average maturity of 3.7/5 indicates a "Managed-to-Defined" level. The dimensional RAG status is RED because three distinct High-severity findings were identified: (1) absence of changelog/versioning documentation, (2) missing example README and run instructions, and (3) incomplete and partially incorrect error documentation. Each of these represents a tangible barrier to developer onboarding and adoption.

## Consolidated Checklist

| # | Area | Item | Rating | Severity | Source |
|---|------|------|--------|----------|--------|
| 1 | API Surfaces | `__all__` Export Completeness | 4/5 | Medium | 5A |
| 2 | API Surfaces | Import Ergonomics | 5/5 | Info | 5A |
| 3 | API Surfaces | Type Annotation Completeness | 4/5 | Medium | 5A |
| 4 | API Surfaces | `py.typed` Markers | 5/5 | Info | 5A |
| 5 | API Surfaces | Protocol Usage | 4/5 | Low | 5A |
| 6 | API Surfaces | Generic Type Parameters | 5/5 | Info | 5A |
| 7 | API Surfaces | Docstring Coverage | 5/5 | Info | 5A |
| 8 | API Surfaces | API Consistency | 4/5 | Low | 5A |
| 9 | API Surfaces | Return Type Clarity | 4/5 | Medium | 5A |
| 10 | API Surfaces | Error Type Hierarchy | 5/5 | Info | 5A |
| 11 | API Surfaces | Overload/Union Clarity | 3/5 | Low | 5A |
| 12 | API Surfaces | Subpackage `__init__.py` Exports | 4/5 | Medium | 5A |
| 13 | Documentation | Getting Started Guide Completeness | 4/5 | Low | 5B |
| 14 | Documentation | Architecture Documentation Accuracy | 4/5 | Low | 5B |
| 15 | Documentation | API Reference Coverage | 3/5 | Medium | 5B |
| 16 | Documentation | Guide Accuracy | 4/5 | Low | 5B |
| 17 | Documentation | PADR/Decisions Documentation | 3/5 | Medium | 5B |
| 18 | Documentation | MkDocs Configuration | 4/5 | Low | 5B |
| 19 | Documentation | Cross-References | 3/5 | Medium | 5B |
| 20 | Documentation | Code Examples in Docs | 3/5 | Medium | 5B |
| 21 | Documentation | Development Constitution Visibility | 2/5 | Medium | 5B |
| 22 | Documentation | Changelog/Versioning Docs | 1/5 | High | 5B |
| 23 | Documentation | Contributing Guide | 2/5 | Medium | 5B |
| 24 | Documentation | Documentation Freshness | 3/5 | Medium | 5B |
| 25 | Examples & Errors | Dog School Example Completeness | 4/5 | Medium | 5C |
| 26 | Examples & Errors | Example Code Quality | 4/5 | Low | 5C |
| 27 | Examples & Errors | Example Coverage of Features | 3/5 | Medium | 5C |
| 28 | Examples & Errors | Integration Tests as Documentation | 4/5 | Low | 5C |
| 29 | Examples & Errors | RFC 7807 Error Response Format | 5/5 | Info | 5C |
| 30 | Examples & Errors | Domain Exception Context | 5/5 | Info | 5C |
| 31 | Examples & Errors | Validation Error Messages | 4/5 | Low | 5C |
| 32 | Examples & Errors | Error Handler Coverage | 5/5 | Info | 5C |
| 33 | Examples & Errors | Stack Trace Safety | 5/5 | Info | 5C |
| 34 | Examples & Errors | Error Response Consistency | 4/5 | Medium | 5C |
| 35 | Examples & Errors | Example README/Instructions | 1/5 | High | 5C |
| 36 | Examples & Errors | Error Documentation | 2/5 | High | 5C |

**RAG Calculation:**

- Total items: 36
- Sum of ratings: 4+5+4+5+4+5+5+4+4+5+3+4+4+4+3+4+3+4+3+3+2+1+2+3+4+4+3+4+5+5+4+5+5+4+1+2 = 134
- Average maturity: 134 / 36 = **3.72** (rounded to **3.7/5**)
- Critical findings: **0**
- High findings: **3** (items #22, #35, #36)
- Items at 4+: 23/36 = **63.9%**
- Items at 3+: 31/36 = **86.1%**
- RAG determination: >2 High findings triggers **RED** (despite avg >= 3.0 and >= 60% at 3+)

## Critical & High Findings

### High Severity

**H-1: No Changelog or Versioning Documentation (Item #22, Source 5B)**

No CHANGELOG.md, CHANGES.md, or HISTORY.md exists at the repository root or in the documentation site. No versioning strategy document describes the release process or how package versions relate to the root version. The project has advanced from 0.1.0 to 0.3.0 without any release notes or version-tracking documentation.

- `CLAUDE.md:7` -- States `v0.1.0` (stale)
- `pyproject.toml:3` -- Shows version `0.3.0` (current)
- `docs/docs/architecture/packages.md` -- Package table has no version column

**H-2: Example README and Run Instructions Missing (Item #35, Source 5C)**

The `examples/dog_school/` directory contains no README.md, no `__main__.py`, no setup instructions, and no standalone run command. The only way to discover how to use the example is by reading source code or integration tests. The `Usage::` block in `examples/dog_school/app.py:7-11` shows an import but does not explain how to start the server or run tests. The quickstart guide (`docs/docs/getting-started/quickstart.md`) describes a separate `my-app` project, not the dog_school example.

**H-3: Incomplete and Partially Incorrect Error Documentation (Item #36, Source 5C)**

No dedicated error-handling guide exists in the published documentation. The partial mapping in `docs/docs/guides/add-api-endpoint.md:62-93` contains two factual errors:

- `docs/docs/guides/add-api-endpoint.md:66` -- States `ValidationError` maps to `400 Bad Request`, but the actual handler at `packages/infra-fastapi/src/praecepta/infra/fastapi/error_handlers.py:259` returns `422 Unprocessable Entity`
- `docs/docs/guides/add-api-endpoint.md:81` -- Uses `raise NotFoundError(f"Order {order_id} not found")` with a single string argument, but `NotFoundError.__init__` at `packages/foundation-domain/src/praecepta/foundation/domain/exceptions.py:95-99` requires two arguments `(resource_type, resource_id)` -- this code would raise a `TypeError` at runtime

Additionally, PADR-103 at `_kb/decisions/patterns/PADR-103-error-handling.md` is stale and describes an older `ErrorDetail`/`BaseError` hierarchy that does not match the implemented `DomainError` hierarchy. The `ProblemDetail` response schema is not documented for API consumers, and no troubleshooting section exists for common runtime errors.

## Medium Findings

**M-1: `__all__` missing on two packages (Source 5A)**
- `packages/integration-tenancy-identity/src/praecepta/integration/tenancy_identity/__init__.py:1` -- Stub package with no `__all__` definition
- `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` -- Only a docstring; does not re-export `JWTAuthMiddleware` or `APIKeyAuthMiddleware`

**M-2: `Any` type annotations where more specific types are possible (Source 5A)**
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:40` -- `handler: Any` (documented as `Callable[[Request, Exception], Awaitable[Response]]` in comment)
- `packages/foundation-application/src/praecepta/foundation/application/contributions.py:52` -- `hook: Any` (documented as `Callable[[Any], AsyncContextManager[None]]` in comment)
- `packages/foundation-application/src/praecepta/foundation/application/issue_api_key.py:28,30,82` -- `EventSourcedApplication` Protocol uses `Any` for repository and aggregate types
- `packages/infra-persistence/src/praecepta/infra/persistence/redis_client.py:58` -- `self._client: Any = None` (could be `redis.asyncio.Redis | None`)

**M-3: Duplicate `EventSourcedApplication` Protocol (Source 5A)**
- `packages/foundation-application/src/praecepta/foundation/application/issue_api_key.py:20` and `packages/foundation-application/src/praecepta/foundation/application/rotate_api_key.py:19` define identical Protocol classes -- DRY violation

**M-4: `dict[str, Any]` return types instead of typed structures (Source 5A)**
- `packages/foundation-application/src/praecepta/foundation/application/config_service.py:149` -- `get_config() -> dict[str, Any] | None` with known keys (`key`, `value`, `source`)
- `packages/foundation-application/src/praecepta/foundation/application/config_service.py:198` -- `get_all_config() -> list[dict[str, Any]]`

**M-5: `IssueAPIKeyHandler.handle()` returns `tuple[str, str]` (Source 5A)**
- `packages/foundation-application/src/praecepta/foundation/application/issue_api_key.py:62` -- Returns `tuple[str, str]` documented as `(key_id, full_plaintext_key)`, while `RotateAPIKeyHandler.handle()` returns a named `RotateAPIKeyResult` dataclass -- inconsistency between the two handlers

**M-6: `infra.auth.middleware` subpackage `__init__.py` missing re-exports (Source 5A)**
- `packages/infra-auth/src/praecepta/infra/auth/middleware/__init__.py:1` -- Empty; does not re-export `JWTAuthMiddleware` or `APIKeyAuthMiddleware`, inconsistent with the pattern used by `infra.fastapi.middleware`

**M-7: API Reference pages missing for 2 packages (Source 5B)**
- `packages/infra-taskiq/` -- No entry in `docs/mkdocs.yml` nav (lines 33-42) or `docs/docs/reference/`
- `packages/integration-tenancy-identity/` -- No reference documentation page
- `docs/mkdocs.yml:50-59` -- `infra-taskiq` package path not listed in mkdocstrings Python handler paths

**M-8: PADRs largely inaccessible from published docs (Source 5B)**
- `docs/docs/decisions.md` -- Only 6 of 25 PADRs surfaced; remaining 18-19 are in the internal `_kb/` knowledge base with no path from published documentation
- `_kb/decisions/_index.md` -- Complete index exists but is not published

**M-9: Cross-reference gaps in documentation (Source 5B)**
- Reference pages (`docs/docs/reference/*.md`) do not link to related guides
- `docs/docs/decisions.md:101` -- Relative link to `architecture/entry-points.md` could be fragile

**M-10: Code examples in docs are illustrative only (Source 5B)**
- No `examples/` directory corresponds to guide snippets; no CI verification that doc code compiles
- `docs/docs/index.md:31-47` -- Missing `Decimal` import in quick example
- `docs/docs/guides/build-projection.md:16-19` -- Uses hypothetical `self.execute()` API that does not exist on `BaseProjection`

**M-11: Development Constitution visibility and accuracy (Source 5B)**
- `_kb/design/references/con-development-constitution.md:1` -- Template placeholder `{Project}` never replaced
- Constitution mandates "Async-First Principle" but PADR-109 establishes "Sync-First Event Sourcing" -- contradiction
- Not linked from CLAUDE.md, MkDocs nav, or any published document

**M-12: Contributing guide absent (Source 5B)**
- No CONTRIBUTING.md at repository root
- No PR template or code review guidelines (`.github/PULL_REQUEST_TEMPLATE.md`)
- Contributing information scattered between CLAUDE.md and `docs/docs/getting-started/installation.md:44-52`

**M-13: Dog School example omits key framework features (Source 5C)**
- No projection example, no auth middleware, no event store persistence, no application services, no observability, no sagas, no feature flags demonstrated
- Only one example application in the entire repository

**M-14: `ValidationError` status-code discrepancy between docs and implementation (Source 5C)**
- `docs/docs/guides/add-api-endpoint.md:66` says 400
- `packages/infra-fastapi/src/praecepta/infra/fastapi/error_handlers.py:259` returns 422
- `_kb/decisions/patterns/PADR-103-error-handling.md:282` also says 400

**M-15: Documentation freshness issues (Source 5B)**
- `CLAUDE.md:7` version stale (`v0.1.0` vs actual `0.3.0`)
- `docs/docs/architecture/entry-points.md:28` documents `praecepta.subscriptions` entry-point group that no package registers
- Getting-started installation guide uses wrong git clone URL (`wetink` vs `wet-ink-corporation`) at `docs/docs/getting-started/installation.md:48`
- Missing infrastructure prerequisites (PostgreSQL, Redis) in installation docs

## Low & Info Findings

**Low severity (7 items):**
- Protocol `@runtime_checkable` usage is inconsistent: foundation-level ports use it, application-level protocols do not (Source 5A, item #5)
- `record_data_deleted` on `Tenant` at `packages/domain-tenancy/src/praecepta/domain/tenancy/tenant.py:299` breaks the `request_*` naming convention for command methods (Source 5A, item #8)
- No `@overload` decorators used anywhere; some functions could benefit from narrower return types (Source 5A, item #11)
- `codehilite` and `fenced_code` extensions in `docs/mkdocs.yml` are legacy; `pymdownx.highlight` + `pymdownx.superfences` preferred (Source 5B, item #18)
- Guides are not end-to-end testable; no CI verification of doc code snippets (Source 5B, item #16)
- Dog School example has no `if __name__ == "__main__"` block or standalone runner (Source 5C, item #26)
- `ValidationError` supports only single-field validation; no batch aggregation pattern (Source 5C, item #31)

**Info severity (9 items):**
- Import ergonomics are excellent with 1-level imports across all packages (Source 5A, item #2)
- All 11 packages have correct `py.typed` markers in PEP 561 locations (Source 5A, item #4)
- Generic type parameters (`Application[UUID]`, `TypeVar("T", bound=BaseModel)`) are correctly parameterized throughout (Source 5A, item #6)
- Docstring coverage is 100% across modules, classes, methods, protocols, and exceptions (Source 5A, item #7)
- Exception hierarchy supports 5 levels of catch granularity with machine-readable error codes (Source 5A, item #10)
- RFC 7807 implementation exceeds the original PADR-103 spec with Pydantic models and proper media types (Source 5C, item #29)
- Domain exceptions carry rich structured context with `__str__` and `__repr__` formatting (Source 5C, item #30)
- All 10 exception types mapped to HTTP handlers with protocol-compliant headers (Source 5C, item #32)
- Stack trace safety is thorough with production/debug mode toggle, server-side logging, and sensitive data sanitization (Source 5C, item #33)

## Cross-Cutting Themes

**Theme 1: Code Quality Outpaces Documentation Quality**
The API surfaces (5A average: 4.3/5) significantly outperform the documentation (5B average: 3.0/5). Type annotations, docstrings, `py.typed` markers, and import ergonomics are all at or near the "Optimizing" level. Meanwhile, critical onboarding documents (changelog, contributing guide, example README) are absent or at the "Initial/Not Implemented" level. The project invests heavily in making the code self-documenting but underinvests in the surrounding scaffolding that guides developers to the code in the first place.

**Theme 2: Factual Errors Undermine Trust in Documentation**
Multiple factual inaccuracies exist across guides and reference materials: the `ValidationError` status-code discrepancy (400 in docs, 422 in code), the incorrect `NotFoundError` constructor call in the guide, the wrong git clone URL, the stale CLAUDE.md version, the phantom `praecepta.subscriptions` entry-point group, and the Constitution's async-first mandate contradicting PADR-109's sync-first decision. Each individually is minor, but collectively they erode developer trust in documentation accuracy.

**Theme 3: Internal Knowledge vs. Published Documentation Gap**
Significant content exists in the `_kb/` internal knowledge base (25 PADRs, Development Constitution, design references) that is not surfaced in the published documentation site. Only 6 of 25 PADRs appear in published docs. The Constitution is entirely internal and contains stale template placeholders. This creates a two-tier information system where contributors with repository access have substantially more context than documentation readers.

**Theme 4: Single Example Carries Too Much Weight**
The dog_school example is the only runnable example in the repository, and it demonstrates only a subset of framework capabilities (aggregates, events, validation, multi-tenancy). Key features -- projections, authentication, persistence, application services, observability, and sagas -- have no example coverage. Combined with the lack of README and run instructions, this creates a narrow onboarding funnel that does not scale to the framework's actual feature surface.

## Strengths

1. **Exceptional docstring coverage and quality** -- 100% coverage across all public modules, classes, methods, protocols, and exceptions. Docstrings follow Google-style conventions with `Args:`, `Returns:`, `Raises:`, and `Example:` sections. Standout examples include the event schema evolution guide in `events.py:1-52` and the hashing algorithm documentation in `config_service.py:72-104`. (Source 5A, item #7)

2. **Best-in-class error handling** -- The RFC 7807 `ProblemDetail` implementation, structured exception context, 10-handler coverage with protocol-compliant headers (WWW-Authenticate, Retry-After), stack-trace safety with sensitive-data sanitization, and 5-level catch granularity in the exception hierarchy represent a mature, production-ready error system. (Sources 5A item #10, 5C items #29, #30, #32, #33)

3. **Ergonomic import design** -- All key types are importable from top-level package namespaces via thorough `__init__.py` re-exports. Consumers never need to import from internal implementation modules. This pattern is consistent across all 11 packages. (Source 5A, item #2)

4. **Full PEP 561 compliance** -- All 11 packages have `py.typed` markers in the correct leaf-package locations, combined with mypy strict-mode configuration. Downstream consumers get full type-checking support out of the box. (Source 5A, item #4)

5. **Integration tests serve as usage documentation** -- The four root-level integration test files (`test_integration_dog_school.py`, `test_integration_error_handling.py`, `test_integration_app_factory.py`, `test_integration_middleware.py`) are well-organized with class docstrings and descriptive test names that effectively demonstrate framework usage patterns. (Source 5C, item #28)

## Recommendations

**P1 -- Address within current sprint (High severity, blocks onboarding)**

1. **Create a CHANGELOG.md** and document at least the changes between 0.1.0 and 0.3.0. Establish a versioning strategy document (SemVer, per-package vs. monorepo-wide). Update `CLAUDE.md:7` to reflect the current version 0.3.0.

2. **Add a README.md to `examples/dog_school/`** with setup instructions, standalone run command (`uvicorn` invocation), test run command, and a description of what the example demonstrates. Add a `__main__.py` for direct execution.

3. **Fix the two factual errors in `docs/docs/guides/add-api-endpoint.md`**: correct the `ValidationError` status code from 400 to 422 (line 66), and fix the `NotFoundError` constructor call to use `(resource_type, resource_id)` instead of a single string (line 81).

4. **Create a dedicated Error Handling Guide** in `docs/docs/guides/` that documents all 10 exception-to-HTTP mappings, the `ProblemDetail` response schema, common error scenarios and resolution steps, and the production vs. debug mode toggle.

**P2 -- Address within next 2 sprints (Medium severity, improves contributor experience)**

5. **Create a CONTRIBUTING.md** at the repository root consolidating dev setup, PR conventions, branch strategy, commit message format, code review process, and a reference to `make verify`. Move the "Adding a New Package" checklist from CLAUDE.md into this file (or reference it).

6. **Replace `Any` types in contribution dataclasses** (`contributions.py:40,52`) with proper `Callable` type aliases. Extract the duplicate `EventSourcedApplication` Protocol from `issue_api_key.py` and `rotate_api_key.py` into a shared module.

7. **Add API Reference pages** for `praecepta-infra-taskiq` and `praecepta-integration-tenancy-identity`. Add the `infra-taskiq` package path to `docs/mkdocs.yml` mkdocstrings handler paths.

8. **Introduce a typed return structure** (TypedDict or dataclass) for `TenantConfigService.get_config()` and `get_all_config()` to replace `dict[str, Any]` returns. Align `IssueAPIKeyHandler.handle()` to return a named result type matching `RotateAPIKeyHandler`.

9. **Publish PADRs to the documentation site** -- either copy the `_kb/decisions/` content into `docs/docs/decisions/` as individual pages, or configure MkDocs to include the `_kb/` directory. Update stale PADR-103 to reflect the implemented `DomainError` hierarchy.

10. **Fix documentation freshness issues**: correct the git clone URL in `docs/docs/getting-started/installation.md:48`, add PostgreSQL/Redis to prerequisites, remove or implement the `praecepta.subscriptions` entry-point group from `docs/docs/architecture/entry-points.md:28`, add `__all__` to `integration.tenancy_identity.__init__.py` and `infra.auth.middleware.__init__.py`.

**P3 -- Address when capacity allows (Low severity, polish)**

11. **Add a second example application** demonstrating projections, authentication, and persistence (e.g., a mini CRM or inventory system) to broaden example feature coverage beyond the dog_school's scope.

12. **Resolve the Development Constitution**: either customize it for Praecepta (replace `{Project}` placeholder, resolve the async-first vs. sync-first contradiction with PADR-109) and publish it, or archive it if it no longer reflects the project's direction.

13. **Standardize `@runtime_checkable`** usage across all Protocol definitions, and add re-exports for `ConfigRepository` and `ConfigCache` to the `foundation.application.__init__.py` public API.

14. **Upgrade MkDocs extensions** from `codehilite` + `fenced_code` to `pymdownx.highlight` + `pymdownx.superfences` for modern syntax highlighting features. Add cross-reference links from API reference pages to related guides.
