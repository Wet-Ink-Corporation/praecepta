# {Project} Development Constitution

> **Status**: Governing Document  
> **Effective**: 2026-01-29  
> **Authority**: All development workflows MUST comply with these articles.

This constitution establishes immutable principles for {Project} development.
Deviation requires explicit ADR justification and user approval.

---

## Article I: Async-First Principle

All I/O operations MUST use asyncio patterns.

**Requirements:**

- Database operations use async SQLAlchemy sessions
- HTTP clients use async libraries (httpx, aiohttp)
- File I/O uses aiofiles where applicable

**Forbidden:**

- Converting async to sync is FORBIDDEN without explicit ADR justification
- Blocking calls in async contexts
- `time.sleep()` in async code (use `asyncio.sleep()`)

---

## Article II: Test-First Imperative

No implementation code SHALL be written before:

1. Test files are created with failing tests
2. Tests are validated against test-plan.md
3. Tests are confirmed to FAIL (Red phase)

**TDD Cycle:**

```
Red → Green → Refactor
```

**Verification:**

- Tests must exist before implementation
- Tests must fail before implementation passes them
- Skipping tests "because they're hard" is FORBIDDEN

---

## Article III: Discovery Before Assertion

Before claiming any capability is "impossible" or "unavailable":

1. **Search codebase** for existing patterns
2. **Consult skill documentation** for library guidance
3. **Check ADRs** for prior architectural decisions
4. **Read architecture docs** via `_kb/MANIFEST.md` → domain BRIEFs

**False claims without discovery constitute HALLUCINATION.**

**Required searches before assertions:**

```bash
rg "pattern_name" src/
rg "error_message" --type py
```

---

## Article IV: Planning Artifacts Are Binding

`architecture-design.md` and `dev-plan.md` are CONTRACTS, not suggestions.

**Requirements:**

- Follow the specified component structure
- Implement the specified interfaces
- Use the specified patterns
- Create the specified test files

**Deviations require:**

1. Explicit documentation of why deviation is necessary
2. Update to the planning artifact reflecting the change
3. User approval before proceeding

---

## Article V: Multi-Tenancy Enforcement

Every database query, every API endpoint, every event handler MUST include tenant_id scoping.

**There are NO exceptions.**

**Verification checklist:**

- [ ] All SELECT queries filter by tenant_id
- [ ] All INSERT operations include tenant_id
- [ ] API endpoints extract tenant from auth context
- [ ] DTOs include tenant_id where applicable
- [ ] Events include tenant_id in payload

---

## Article VI: Pattern Consistency

When implementing a new capability, first discover existing patterns:

1. **Find** analogous implementations in codebase
2. **Extract** the pattern (repository, service, handler, test fixture)
3. **Apply** the pattern to new implementation

**Deviation requires documented justification.**

**Pattern discovery locations:**

- Repository patterns: `src/{project}/*/infrastructure/`
- Service patterns: `src/{project}/*/application/`
- API patterns: `src/{project}/*/api/`
- Test patterns: `tests/integration/conftest.py`

---

## Constitutional Compliance Checklist

Before any implementation work, confirm:

- [ ] Article I: No sync I/O patterns introduced
- [ ] Article II: Test files created before implementation
- [ ] Article III: Searched codebase before making capability claims
- [ ] Article IV: Following architecture-design.md exactly
- [ ] Article V: All queries include tenant_id
- [ ] Article VI: Found and applied existing patterns

---

## Enforcement

This constitution is referenced in:

- All skill preambles
- Pre-implementation gates in `/backlog-implement`
- Implementation review checklist in `/backlog-implementation-review`

**Violations result in:**

- Implementation review BLOCKED verdict
- Required remediation before proceeding
- Documented lessons learned in retrospective
