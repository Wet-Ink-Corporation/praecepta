# Documentation Quality -- Developer Experience

**Collector ID:** 5B
**Dimension:** Developer Experience
**Date:** 2026-02-18
**Auditor:** Claude Opus 4.6 (automated)

---

## 1. Getting Started Guide Completeness

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

The getting-started section comprises three well-structured pages: installation, quickstart, and core concepts. Prerequisites are listed (`docs/docs/getting-started/installation.md` lines 3-6: Python 3.12+, uv). The quickstart walks through project creation, event definition, aggregate creation, app factory, and running the server. Next steps link to deeper guides.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| Incorrect git clone URL | `docs/docs/getting-started/installation.md:48` | Uses `github.com/wetink/praecepta.git` but the repo is at `github.com/wet-ink-corporation/praecepta` (per `docs/mkdocs.yml:4`) |
| Missing `Decimal` import in index example | `docs/docs/index.md:31-47` | The quick example uses `Decimal` without importing it; the quickstart (`quickstart.md:19`) correctly includes `from decimal import Decimal` |
| No infrastructure prerequisites documented | `docs/docs/getting-started/installation.md` | PostgreSQL and Redis are required for event store and persistence, but are not listed as prerequisites |
| Missing database setup step | `docs/docs/getting-started/quickstart.md` | The guide ends with "visit localhost:8000/docs" but does not mention that a PostgreSQL database is needed for the event store to function, which would cause runtime errors |

---

## 2. Architecture Documentation Accuracy

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

Architecture docs accurately reflect the actual code structure. The 4-layer hierarchy, package list, dependency rules, and import-linter contracts all match reality. The actual `pyproject.toml` contracts (`pyproject.toml:188-215`) exactly match what is described in `docs/docs/architecture/overview.md:39-59`. The accepted exception for domain-to-infra-eventsourcing dependency is documented consistently in CLAUDE.md, architecture overview, and matches the actual package dependencies.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| 11 packages listed; matches code | `docs/docs/architecture/packages.md` and `packages/` directory | All 11 packages present in both docs and filesystem |
| Entry-point groups list includes undocumented group | `docs/docs/architecture/entry-points.md:28` | Documents `praecepta.subscriptions` group but no package actually registers entries under this group, and `CLAUDE.md` does not mention it |
| Version discrepancy between CLAUDE.md and pyproject.toml | `CLAUDE.md:7` vs `pyproject.toml:3` | CLAUDE.md says "v0.1.0" but `pyproject.toml` shows version `0.3.0` |
| Layer ordering description is accurate | `docs/docs/architecture/overview.md` | Matches actual import-linter contracts in `pyproject.toml:210-215` |

---

## 3. API Reference Coverage

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

API reference pages exist for 9 of 11 packages. Most are thin stubs that rely on `mkdocstrings` auto-generation via `::: praecepta.{namespace}` directives. The `infra-eventsourcing` reference is notably richer with a hand-written key exports table and architecture note. However, `praecepta-infra-taskiq` and `praecepta-integration-tenancy-identity` have no reference pages at all.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| No reference page for `infra-taskiq` | `docs/mkdocs.yml` nav (line 33-42) | Package exists at `packages/infra-taskiq/` but has no entry in the API Reference nav or `docs/docs/reference/` |
| No reference page for `integration-tenancy-identity` | `docs/mkdocs.yml` nav (line 33-42) | Package exists at `packages/integration-tenancy-identity/` but has no reference doc |
| `mkdocstrings` paths missing `infra-taskiq` | `docs/mkdocs.yml:50-59` | The `infra-taskiq` package path is not listed in the mkdocstrings Python handler paths |
| Most reference pages are minimal stubs | `docs/docs/reference/foundation-domain.md` (10 lines), `infra-auth.md` (9 lines), etc. | Only import example and `::: directive`; no hand-written explanation of key types or usage patterns |
| `infra-eventsourcing` reference is exemplary | `docs/docs/reference/infra-eventsourcing.md` | 41 lines with key exports table, architecture note explaining two paths to event store, and API reference directive |

---

## 4. Guide Accuracy

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** Medium

Eight guides cover domain package creation, aggregates, events, projections, API endpoints, multi-tenancy, production configuration, and testing. Code snippets use current API names that match actual exports (verified: `BaseAggregate`, `BaseEvent`, `TenantId`, `InvalidStateTransitionError`, `create_app`, `AppSettings` all exist in their documented packages). Guides are internally consistent and reference each other.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| Projection guide uses hypothetical `self.execute()` API | `docs/docs/guides/build-projection.md:16-19` | `BaseProjection` does not expose an `execute()` method in its public API; projection handlers interact with SQL through the eventsourcing library's infrastructure |
| Testing guide projection example uses hypothetical `session` kwarg | `docs/docs/guides/build-projection.md:119` | `OrderSummaryProjection(session=db_session)` -- constructor signature not verified against actual `BaseProjection` |
| Guides are not end-to-end testable | All guide files | Code snippets are illustrative but not extracted into runnable examples under an `examples/` directory; no CI verification that snippets compile |
| Production config guide is thorough | `docs/docs/guides/production-configuration.md` | Covers env vars, poll tuning, deployment patterns (single-process, separate worker), and Dockerfile layering |

---

## 5. PADR/Decisions Documentation

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

All 25 PADRs exist as individual markdown files under `_kb/decisions/` (4 strategic + 21 pattern), and an index page at `_kb/decisions/_index.md` lists them all with status. However, PADRs are in the internal `_kb/` knowledge base, not in the published documentation site. The `docs/docs/decisions.md` page only surfaces 6 of the 25 PADRs and describes the remaining 19 as maintained in the "project's internal knowledge base."

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| Only 6 of 25 PADRs surfaced in docs | `docs/docs/decisions.md` | PADR-001, 002, 101, 102, 109, 113, 122 summarized; remaining 18 are inaccessible to docs readers |
| Full PADR index exists but is not published | `_kb/decisions/_index.md` | Complete index with all 25 PADRs, but lives outside the docs site |
| Broken cross-reference in decisions.md | `docs/docs/decisions.md:101` | Link `[Entry-Point Discovery](architecture/entry-points.md)` uses a relative path from the decisions page; since decisions.md is at the docs root, this should work, but mkdocs relative links can be fragile depending on `use_directory_urls` setting |
| No individual PADR pages in docs site | `docs/docs/decisions/` directory does not exist | Only the single summary page; no per-PADR detail pages |

---

## 6. MkDocs Configuration

**Rating: 4/5 -- Managed**
**Severity:** Low | **Confidence:** High

`docs/mkdocs.yml` is well-configured with a clear navigation structure, `shadcn` theme, `mkdocstrings` for auto-generated Python API docs, `llmstxt` plugin for LLM consumption, and standard markdown extensions. The site builds successfully (evidenced by the `docs/site/` directory containing HTML output, `sitemap.xml`, `llms.txt`, etc.).

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| `codehilite` extension used alongside `shadcn` theme | `docs/mkdocs.yml:106` | `codehilite` is a legacy extension; modern MkDocs setups typically use `pymdownx.highlight` + `pymdownx.superfences` instead |
| `fenced_code` extension is redundant | `docs/mkdocs.yml:107` | Python-Markdown's `fenced_code` is typically superseded by `pymdownx.superfences` which is not listed |
| Missing `attr_list` extension | `docs/mkdocs.yml:104-113` | Needed for some advanced MkDocs Material/shadcn features like button styling |
| `llmstxt` plugin provides LLM-optimized output | `docs/mkdocs.yml:64-102` | Good practice for AI-assisted documentation consumption; `llms.txt` and `llms-full.txt` generated in site output |
| Site builds successfully | `docs/site/` directory | Contains `index.html`, all section directories, `sitemap.xml`, `objects.inv` |

---

## 7. Cross-References

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Internal cross-references exist between docs (quickstart links to concepts and guides; guides link to architecture pages). However, several issues exist with link consistency and completeness.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| Quickstart links to guides correctly | `docs/docs/getting-started/quickstart.md:98-100` | Links to `concepts.md`, `../guides/define-aggregate.md`, `../guides/create-domain-package.md` use correct relative paths |
| Namespace packages page cross-referenced | `docs/docs/architecture/packages.md:3` | Links to `namespace-packages.md` correctly |
| Create-domain-package links to namespace docs | `docs/docs/guides/create-domain-package.md:26` | `../architecture/namespace-packages.md` is correct |
| Decisions page link to entry-points may break | `docs/docs/decisions.md:101` | Uses `architecture/entry-points.md` -- this is relative to decisions.md location and should resolve correctly, but is not prefixed with `../` which some builds may require |
| No links from reference pages to guides | All `docs/docs/reference/*.md` | Reference stubs do not link to related guides (e.g., foundation-domain reference does not link to define-aggregate guide) |
| Index page links are valid | `docs/docs/index.md:5` | Links to `getting-started/installation.md` and GitHub repo URL |

---

## 8. Code Examples in Docs

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** Medium

Code examples throughout the documentation are well-formatted and follow consistent patterns. They use actual API names that exist in the codebase. However, examples are illustrative rather than executable -- none are extracted into runnable files, and some contain subtle issues.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| Missing `Decimal` import on index page | `docs/docs/index.md:31-47` | Example uses `Decimal` type without importing it |
| Quickstart example is complete | `docs/docs/getting-started/quickstart.md` | All 5 steps have full, copy-pasteable code with imports |
| Projection `self.execute()` is hypothetical | `docs/docs/guides/build-projection.md:16-19` | This method name may not match the actual `BaseProjection` API |
| Testing examples are realistic | `docs/docs/guides/testing.md:49-69, 76-107` | Aggregate tests are pure and would work; endpoint tests show proper `httpx.AsyncClient` usage with `ASGITransport` |
| Entry-point examples are accurate | `docs/docs/architecture/entry-points.md:34-43` | `pyproject.toml` snippets match actual package conventions |
| No `examples/` directory with runnable code | Repository root | Despite `ruff` config referencing `examples/` in `pyproject.toml:80`, no examples directory exists |

---

## 9. Development Constitution Visibility

**Rating: 2/5 -- Initial**
**Severity:** Medium | **Confidence:** High

A Development Constitution exists at `_kb/design/references/con-development-constitution.md` but it is entirely within the internal `_kb/` knowledge base. It is not referenced from the published documentation site, not linked from CLAUDE.md, and not included in the MkDocs navigation. It also uses placeholder `{Project}` text rather than "Praecepta", suggesting it was templated but never customized.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| Constitution exists but is internal-only | `_kb/design/references/con-development-constitution.md` | Not published in `docs/docs/` or linked from MkDocs nav |
| Template placeholder not replaced | `_kb/design/references/con-development-constitution.md:1` | Title is `{Project} Development Constitution` instead of `Praecepta Development Constitution` |
| Article I conflicts with PADR-109 | `_kb/design/references/con-development-constitution.md:12-14` | Constitution mandates "Async-First Principle" and "All I/O operations MUST use asyncio patterns", but PADR-109 establishes "Sync-First Event Sourcing" where commands and projections are synchronous |
| Not linked from CLAUDE.md | `CLAUDE.md` | The CLAUDE.md developer guide does not reference the constitution |
| Not discoverable by new contributors | -- | No path from any public document leads to this file |

---

## 10. Changelog/Versioning Docs

**Rating: 1/5 -- Not Implemented**
**Severity:** High | **Confidence:** High

There is no CHANGELOG.md, CHANGES.md, or HISTORY.md at the repository root or in the docs directory. No versioning strategy document exists. The version in `pyproject.toml` is `0.3.0` while CLAUDE.md still references `v0.1.0`, indicating the version has advanced without changelog tracking.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| No CHANGELOG.md exists | Repository root | No changelog file of any name found |
| No versioning strategy documented | All docs | No page describing release process, versioning scheme (SemVer?), or how package versions relate to the root version |
| Version mismatch between CLAUDE.md and pyproject.toml | `CLAUDE.md:7` says `v0.1.0`; `pyproject.toml:3` says `0.3.0` | Indicates at least two version bumps occurred without updating the developer guide |
| No per-package version tracking | `docs/docs/architecture/packages.md` | Package table does not include version column; unclear if all 11 packages share the root version |

---

## 11. Contributing Guide

**Rating: 2/5 -- Initial**
**Severity:** Medium | **Confidence:** High

There is no CONTRIBUTING.md file at the repository root. Contributing information is scattered: `CLAUDE.md` documents commands and package layout conventions, and `docs/docs/getting-started/installation.md` has a brief "Development Setup" section (lines 44-52). However, there is no unified contributing guide covering code review process, PR conventions, branch strategy, commit message format, or how to run the full verification suite.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| No CONTRIBUTING.md exists | Repository root | Standard open-source contributing guide is absent |
| Partial dev setup in installation docs | `docs/docs/getting-started/installation.md:44-52` | Three commands: `git clone`, `make install`, `make verify` |
| CLAUDE.md has good command reference | `CLAUDE.md:12-22` | Lists all `make` targets with descriptions |
| CLAUDE.md documents "Adding a New Package" | `CLAUDE.md:100-110` | 4-step checklist for new packages, but this is AI-agent guidance, not contributor docs |
| No PR template or code review guidelines | Repository root | No `.github/PULL_REQUEST_TEMPLATE.md` or similar |
| Git clone URL uses wrong org in docs | `docs/docs/getting-started/installation.md:48` | `wetink` instead of `wet-ink-corporation` |

---

## 12. Documentation Freshness

**Rating: 3/5 -- Defined**
**Severity:** Medium | **Confidence:** High

Most documentation reflects the current implementation. Package names, layer structure, entry-point groups, and API names match the code. However, several staleness indicators exist, most notably the version discrepancy and the `praecepta.subscriptions` phantom entry-point group.

**Findings:**

| Finding | Location | Detail |
|---------|----------|--------|
| CLAUDE.md version is stale | `CLAUDE.md:7` | Says `v0.1.0` but `pyproject.toml` is at `0.3.0` |
| `praecepta.subscriptions` entry-point group documented but unused | `docs/docs/architecture/entry-points.md:28` | No package registers under this group; either the implementation was removed or it was speculatively documented |
| Missing packages in reference docs | `docs/mkdocs.yml:33-42` | `infra-taskiq` and `integration-tenancy-identity` packages exist in code but have no reference pages |
| Constitution has `{Project}` placeholder | `_kb/design/references/con-development-constitution.md:1` | Never customized for Praecepta |
| Projection guide reflects recent architectural change | `docs/docs/guides/build-projection.md:88-96` | Documents the polling-based approach which matches the most recent commit (`93d2192 fix: replace in-process projection runner with polling-based consumption`) |
| Production config guide is current | `docs/docs/guides/production-configuration.md` | `PROJECTION_POLL_*` environment variables match `ProjectionPollingSettings` in the codebase |

---

## Summary

| # | Item | Rating | Severity |
|---|------|--------|----------|
| 1 | Getting Started Guide Completeness | 4/5 | Low |
| 2 | Architecture Documentation Accuracy | 4/5 | Low |
| 3 | API Reference Coverage | 3/5 | Medium |
| 4 | Guide Accuracy | 4/5 | Low |
| 5 | PADR/Decisions Documentation | 3/5 | Medium |
| 6 | MkDocs Configuration | 4/5 | Low |
| 7 | Cross-References | 3/5 | Medium |
| 8 | Code Examples in Docs | 3/5 | Medium |
| 9 | Development Constitution Visibility | 2/5 | Medium |
| 10 | Changelog/Versioning Docs | 1/5 | High |
| 11 | Contributing Guide | 2/5 | Medium |
| 12 | Documentation Freshness | 3/5 | Medium |

**Overall dimension average: 3.0/5 (Defined)**

The documentation site has a solid foundation with comprehensive getting-started content, accurate architecture docs, and thorough guides. The primary gaps are: (1) no changelog or versioning documentation, (2) no contributing guide, (3) incomplete API reference coverage (2 packages missing), (4) PADRs locked in an internal knowledge base rather than published, and (5) the Development Constitution is both inaccessible and contains contradictions with accepted PADRs. The most actionable high-severity item is establishing changelog tracking given the project has already advanced from 0.1.0 to 0.3.0 without any release documentation.
