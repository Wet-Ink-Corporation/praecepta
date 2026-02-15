# Project Execution Patterns

> Distilled meta-patterns from multi-feature agent-orchestrated development retrospectives.

---

## 1. Feature-Aware Planning Acceleration

**Context:** When a feature has 3+ stories sharing architecture, test strategy, and domain context.

**Pattern:** Invest in feature-level planning artifacts (research, architecture, test strategy) that are reused across all stories in the feature. This eliminates 45-60% of per-story planning overhead.

| Metric | Observed Range |
|--------|---------------|
| Planning artifact reuse | 3-5x per feature |
| Per-story planning reduction | 45-60% |
| ROI on feature planning | 2-3x (planning time vs execution savings) |

---

## 2. Velocity Learning Curve

**Context:** Sequential stories within the same feature and bounded context.

**Pattern:** Later stories complete significantly faster than earlier ones due to accumulated context, established patterns, and fixture reuse.

| Story Position | Typical Velocity (vs Story 1) |
|---------------|-------------------------------|
| Story 1 | Baseline (100%) |
| Story 2-3 | 50-70% of Story 1 time |
| Story 4-5 | 35-46% of Story 1 time |

**Implication:** Estimate later stories at 40-60% of first story effort.

---

## 3. Test Baseline Gate

**Context:** Starting a new feature where prior features may have introduced regressions.

**Pattern:** Run full test suite validation before feature planning begins. Pre-existing failures can delay feature start by 3+ hours and mask new bugs.

**Evidence:** Baseline gates consistently discover residual bugs from prior features — race conditions, API misuse, cross-tenant leakage — before they compound.

**Rule:** Never skip the baseline gate, even under schedule pressure.

---

## 4. Fixture Isolation Strategy

**Context:** Integration tests using shared infrastructure (databases, event stores, message queues).

**Pattern:** Use session-scoped containers with function-scoped cleanup to prevent test bleed between test cases.

```
Container lifecycle:  session-scoped (start once)
Database cleanup:     function-scoped (reset per test)
Fixture factories:    function-scoped (fresh data per test)
```

---

## 5. Vertical Slice Consistency

**Context:** Implementing features across bounded contexts in a modular monolith.

**Pattern:** Every feature slice follows the same file structure: `cmd.py` / `query.py` / `endpoint.py`. Consistency reduces cognitive load and enables pattern-based code generation.

---

## 6. RLS-First Migration Strategy

**Context:** Adding new tenant-scoped tables to a multi-tenant database.

**Pattern:** Add Row-Level Security (RLS) policy in the same migration that creates the table. Never create a table without its RLS policy — the gap between creation and policy is a security vulnerability window.

---

## 7. Integration Test Template Gap

**Context:** Complex fixture wiring (event store + database + API framework) for integration tests.

**Pattern:** This combination consistently requires multiple remediation cycles. Invest in reusable integration test templates/factories that wire these components together. The template pays for itself after 2 features.

---

## 8. Token Exhaustion on Large Stories

**Context:** Stories with >1,000 lines of code scope in agent-orchestrated development.

**Pattern:** Stories exceeding ~1,000 LOC risk mid-execution token exhaustion requiring manual restart. Mitigate by:
1. Breaking large stories into sub-tasks with explicit phase boundaries
2. Using context compaction at phase transitions
3. Targeting ≤800 LOC per agent session

---

## 9. Projection-Based Fast-Path Lookups

**Context:** Authentication and provisioning flows that need O(1) lookups before full aggregate hydration.

**Pattern:** Use indexed projection table lookups instead of aggregate hydration (O(n) events) for hot-path operations. Synchronous projection updates ensure consistency. Bypass RLS for pre-tenant-context lookups (e.g., resolving tenant from JWT claims).

---

## 10. Event Naming Discipline

**Context:** Domain events across all bounded contexts.

**Pattern:** Past-tense verbs consistently applied: `Created`, `Updated`, `Archived`, `Suspended`, `Decommissioned`. Never use present tense or imperative mood for events (those are commands).

---

## 11. Foundation Story First

**Context:** Features with 3+ stories that share infrastructure (aggregates, services, migrations).

**Pattern:** First story creates all shared infrastructure. Subsequent stories implement slices on top of the shared foundation, enabling safe parallelization.

| Step | Action | Why |
|------|--------|-----|
| 1 | First story creates shared infra | Aggregate, base events, migration, repository interface |
| 2 | Remaining stories build slices | Each story touches different files, no merge conflicts |

---

## 12. Zero Remediation Loops

**Context:** Achieving clean implementation passes without rework.

**Pattern:** Features that invest in thorough planning (research → PRD → architecture → test-plan → dev-plan) consistently achieve zero remediation loops during implementation. The planning investment pays for itself by eliminating rework cycles.
