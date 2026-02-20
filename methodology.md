# Codebase Quality Audit — Methodology Guide

**Version:** 1.0 | **First used:** 2026-02-18 | **Context:** Post-Epic-4 retrospective

This document describes the methodology and execution approach for running a multi-agent codebase quality audit on the redkiln project. Future agents should use this as a reference when conducting subsequent retrospectives.

---

## 1. Purpose

Audit the **implemented source code** (not planning artifacts) to answer: *What is the quality of our output and how closely aligned to the vision and guidelines are we?*

This is distinct from the per-epic audits (audit-E01 through audit-E09) which examine planning artifacts (frontmatter, YAML validity, KB grounding). This audit targets code, tests, and infrastructure.

---

## 2. Two-Tier Agent Architecture

### Problem

A single long-running agent reading 30-70+ files accumulates tool calls, file reads, and responses that fill the context window. Context rot leads to conflation (confusing workspace findings with backlog), lost findings, and incomplete checklists.

### Solution

Decompose each auditor role into **short-lived Collector sub-agents** (fresh context per bounded context/module) and a **Synthesis agent** (reads only intermediate artifacts, not raw code). Files on disk are the handoff mechanism between tiers.

```
Tier 1: Collectors (fresh context, ~10-15 files each, write intermediate artifacts)
    |
    v  (files on disk)
    |
Tier 2: Synthesis (reads intermediate artifacts only, writes final audit)
    |
    v  (files on disk)
    |
Consolidation: Reads all 6 final audits, produces unified report + remediation backlog
```

### Why This Works

| Risk | Mitigation |
|------|-----------|
| Context rot | Each collector has a fresh context (~15 files + KB). No accumulated history. |
| Conflation | Each collector sees only one bounded context. Impossible to confuse workspace with backlog. |
| Cross-agent contamination | Each agent starts with zero conversation history. |
| Lost findings | Findings written to files on disk, not held in memory. |
| Incomplete checklists | Synthesis agent's sole job is merging — it re-reads scorecards and catches blanks. |

---

## 3. Audit Roles (6 Dimensions)

Each role has a focused question, a concrete checklist, and a defined file scope.

| # | Role | Question | Checklist Items | Collectors |
|---|------|----------|-----------------|------------|
| 1 | Architecture Compliance | Does code structure match KB-prescribed architecture? | 14 | 3 (workspace, backlog, infra+foundation) |
| 2 | Domain Model Quality | Are DDD/ES patterns correctly applied? | 12 | 2 (workspace, backlog) |
| 3 | Convention & Standards | Does code follow CLAUDE.md and the Development Constitution? | 13 | 3 (workspace endpoints, backlog endpoints, infra middleware) |
| 4 | Test Quality | Do tests follow TDD principles and achieve coverage targets? | 12 | 3 (workspace tests, backlog tests, infra+integration tests) |
| 5 | Frontend Quality | Does the console follow FEDRs and component patterns? | 13 | 3 (components, features/backlog, api+e2e) |
| 6 | Completeness & Gaps | What's specified but missing? | 10 | 1 (ROADMAP vs reality) |

**Total: 15 collectors + 6 synthesis + 1 consolidation = 22 agents**

### Scaling for Future Epics

As more bounded contexts gain implementation:
- Add collectors per new context (e.g., when pipeline is implemented, add 1A-pipeline, 2A-pipeline, etc.)
- Collector count grows linearly with implemented contexts
- Synthesis agent count stays fixed at 6
- Keep collectors scoped to ~10-15 files each to stay within context limits

---

## 4. Collector Prompt Structure

Every collector prompt must include:

1. **Role identification** — Which auditor role and which context/module
2. **Full checklist** — All items for the role (so it evaluates all items against its file scope)
3. **Explicit file list** — "Read ONLY these files" with full paths
4. **KB references** — Specific BRIEF and PADR files to read for evaluation context
5. **Output path** — Exact path to write the intermediate artifact
6. **Output format** — The standardized artifact structure (see Section 7)
7. **Maturity scale** — The 1-5 rating definitions
8. **Guardrails:**
   - "Do NOT read files outside your assigned list"
   - "Every finding MUST include `file:line` references"
   - "No reference = Low confidence"
   - "Write your artifact to disk BEFORE doing anything else"
   - "Rate ALL checklist items (N/A with explanation if not applicable)"
   - "If you observe something outside your scope, note it in a Cross-Agent Notes section"

### File Scoping Guidelines

- **Workspace collectors:** ~15-20 files covering domain/, application/, infrastructure/, api/, slices/
- **Backlog collectors:** ~18-24 files (more aggregates, more slices)
- **Infra collectors:** ~20-25 files including foundation/, all infra/ subdirectories, scaffold __init__.py files
- **Test collectors:** ~15-25 test files + conftest hierarchy
- **Frontend collectors:** ~20-34 files per module area
- **Completeness collector:** Single collector reading ROADMAP, configs, migrations, and sampling key files

For large contexts, sample rather than read everything. The backlog has 14+ slice endpoints — read 6-8 representative ones rather than all 14.

---

## 5. Synthesis Prompt Structure

Every synthesis prompt must include:

1. **Input files** — Exact paths to the intermediate artifacts to read
2. **Merge instructions:**
   - How to merge scores across collectors for the same checklist item
   - How to handle scoring conflicts (e.g., item rated 5 in workspace but 3 in backlog)
   - How to weight contexts (e.g., backlog has 5 aggregates vs workspace's 1)
3. **Deduplication rules** — Same issue in multiple contexts = one finding with multiple evidence points
4. **Self-validation checklist:**
   - All checklist items have a final score
   - Finding count matches summary section
   - No duplicate findings
   - All severity levels valid
   - RAG correctly computed
5. **Output format** — The standardized audit file structure
6. **Key rule:** "Do NOT read raw source code — only the intermediate artifacts"

---

## 6. Rating System (3-Tier Hybrid)

### Tier 1 — Individual Findings

```
Severity:   Critical | High | Medium | Low | Info
Confidence: High (verified in code) | Medium (sampled/pattern-based) | Low (inferred)
```

### Tier 2 — Checklist Items (1-5 Maturity)

```
1 = Not Implemented    (absent or fundamentally broken)
2 = Initial            (ad-hoc, inconsistent)
3 = Defined            (documented and partially followed)
4 = Managed            (consistently followed, tooling-enforced)
5 = Optimizing         (fully embedded, actively improved)
```

### Tier 3 — Executive RAG

```
GREEN:  No Critical/High findings; avg maturity >= 4.0; >= 80% checklist at 4+
AMBER:  No Critical; <=2 High; avg maturity >= 3.0; >= 60% at 3+
RED:    Any Critical, or >2 High, or avg maturity < 3.0
```

---

## 7. Standardized Artifact Formats

### Intermediate (Collector Output)

```markdown
# {Role} — {Context}
Collector: {ID} | Date: {date} | Files Examined: {N}

## Checklist Scorecard
| # | Item | Maturity (1-5) | Evidence | Notes |
|---|------|----------------|----------|-------|

## Findings
### FINDING-{PREFIX}-{NNN}: {title}
| Severity | Confidence | Checklist Item | PADR/RKD |
|----------|------------|----------------|----------|
**Observation:** ...
**Evidence:** `file:line` — description
**Expected:** ...
**Recommendation:** ...

## Cross-Agent Notes
## Summary
```

### Final Audit (Synthesis Output)

Same as intermediate but with per-collector score columns, confidence declaration, and RAG status.

### Consolidated Report

Executive summary, dimensional scorecard, cross-cutting themes, all findings by severity, confidence summary.

### Remediation Backlog

Priority matrix (P1/P2/P3), dependency graph, effort summary, quick wins.

---

## 8. Execution Workflow

### Phase 0: Setup
1. Create folder structure (`intermediate/`, `audits/`)
2. Map all source files (Glob patterns for each language/area)
3. Identify KB references needed by each collector
4. Write README with process notes

### Phase 1a: Collectors (parallel)
Launch all collectors as background agents. In the 2026-02-18 run:
- All 15 collectors ran concurrently (launched in 3 batches of 6/5/4)
- Each took 2-4 minutes
- All wrote intermediate artifacts to `intermediate/{role-number}-{role-name}/{context}.md`

### Phase 1b: Synthesis (parallel, after collectors complete per role)
Launch all 6 synthesis agents once their role's collectors complete. Can run all 6 in parallel.

### Phase 2: Consolidation
Single agent reads all 6 final audits. Produces `consolidated-report.md` and `remediation-backlog.md`.

### Phase 3: Verification
1. Confirm all audit files exist with complete checklists (no empty rows)
2. Spot-check 3 random findings — verify `file:line` references are accurate
3. Review remediation backlog for actionability

---

## 9. Folder Structure

```
_workspace/retrospective/
  README.md                               # Process overview, execution log
  methodology.md                          # This file
  intermediate/                           # Tier 1 collector outputs
    01-architecture/
      workspace.md
      backlog.md
      infra-foundation.md
    02-domain-model/
      workspace.md
      backlog.md
    03-conventions/
      workspace-endpoints.md
      backlog-endpoints.md
      infra-middleware.md
    04-test-quality/
      workspace-tests.md
      backlog-tests.md
      infra-integration-tests.md
    05-frontend/
      components.md
      features-backlog.md
      api-e2e.md
    06-completeness/
      gaps.md
  audits/                                 # Tier 2 synthesis outputs
    01-architecture-compliance.md
    02-domain-model-quality.md
    03-conventions-standards.md
    04-test-quality.md
    05-frontend-quality.md
    06-completeness-gaps.md
  consolidated-report.md                  # Phase 2 output
  remediation-backlog.md                  # Phase 2 output
```

---

## 10. Lessons Learned (2026-02-18 Run)

### What Worked Well

1. **Fresh context per collector eliminated conflation.** No collector confused workspace patterns with backlog patterns. Each agent had a clean, focused scope.

2. **Files on disk as handoff mechanism.** Intermediate artifacts survived any agent context issues. Synthesis agents could re-read them cleanly.

3. **Explicit file lists in prompts.** Collectors stayed within scope. No agent wandered into unassigned files.

4. **KB references in collector prompts.** Agents could evaluate against documented patterns (PADRs, FEDRs) rather than guessing at standards.

5. **Self-validation in synthesis prompts.** Synthesis agents caught their own counting errors and scoring inconsistencies before writing final artifacts.

6. **Parallel execution.** All 15 collectors ran concurrently. The entire Phase 1a completed in the time of the slowest collector (~4 minutes), not 15x sequential.

7. **Structured deduplication.** Cross-cutting themes emerged naturally when the consolidation agent saw the same root cause from multiple audit dimensions.

### What Could Be Improved

1. **Collector file counts varied widely.** Some collectors read 15 files, others read 42. The 5C (Frontend API+E2E) collector was the largest at 42 files — consider splitting further for codebases with larger frontend modules.

2. **Completeness role had only 1 collector.** This was the longest-running collector (242 seconds, 76 tool calls) because it needed to sample across the entire codebase. Consider splitting into backend-completeness and frontend-completeness collectors.

3. **Finding ID namespacing across collectors.** Collectors within the same role used different prefixes (ARCH-001 vs ARCH-B-001 vs ARCH-C-001). This worked but required manual renumbering during synthesis. Consider pre-assigning number ranges (e.g., workspace=001-099, backlog=100-199, infra=200-299).

4. **Some checklist items were N/A for specific collectors.** Item 14 (scaffold emptiness) was only evaluable by the infra collector. Consider pre-assigning checklist items to specific collectors rather than giving all items to all collectors.

5. **Background agent output files were empty when checked too early.** The Task tool's output files don't populate until the agent completes. Use `TaskOutput` with blocking instead of reading output files directly.

---

## 11. Adapting for Future Retrospectives

### After each new epic

1. **Update the collector file lists** to include newly implemented files
2. **Add new collectors** for newly implemented bounded contexts
3. **Update checklists** if new PADRs or FEDRs have been adopted
4. **Compare against previous audit** — track maturity score trends over time
5. **Verify previous remediation items** — check if P1/P2 items from the last audit were addressed

### Tracking Progress Across Retrospectives

Consider adding a trend section to the consolidated report:

```markdown
## Trend (vs Previous Audit)
| Dimension | Previous | Current | Delta |
|-----------|----------|---------|-------|
| Architecture | — | 4.29 | baseline |
| Domain Model | — | 4.50 | baseline |
...
```

### Scope Adjustment

- **Full audit** (like this one): All 6 dimensions, all implemented contexts. Run after completing a major epic or at significant milestones.
- **Focused audit**: 1-2 dimensions, 1 context. Run after completing a single feature to verify quality before moving on. Use 1-2 collectors + 1 synthesis agent.
- **Regression audit**: Re-run only the collectors for contexts that changed since the last audit. Compare scores.

---

## 12. Key Reference Files

These files contain the standards against which code is audited:

| Category | Key Files |
|----------|-----------|
| Architecture | `.redkiln/kb/domains/ddd-patterns/BRIEF.md`, `event-store-cqrs/BRIEF.md`, `api-framework/BRIEF.md` |
| PADRs | PADR-101 (slices), 102 (hexagonal), 103 (errors), 108 (protocols), 109 (sync-first), 111 (aggregate type), 113 (validation), 114 (lifecycle) |
| FEDRs | FEDR-001 through FEDR-008 |
| Testing | `.redkiln/kb/domains/test-strategy/BRIEF.md`, PADR-104 |
| Conventions | `CLAUDE.md`, `.redkiln/kb/design/references/con-development-constitution.md` |
| Completeness | `references/ROADMAP.md`, `pyproject.toml` (entry points) |
