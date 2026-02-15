# Tiered Knowledge Architecture — Templates and Standards

Reusable templates for implementing a tiered context architecture in any project's `_kb/` knowledge base. See `tiered-context-guideline.md` for the theoretical foundation.

---

## 1. Tier 0: MANIFEST Template

**Budget:** ≤2,000 tokens. Loaded by every agent on every invocation.

```markdown
# {Project} Knowledge Base

> NAVIGATION PROTOCOL: Read this manifest first. Load domain briefs by keyword match.
> Only load Tier 2 references when a brief's Reference Index directs you to.
> NEVER load all files — always navigate via this index.

## Domains
|domain|brief|scope|hash|updated
|{name}|domains/{name}/BRIEF.md|{one-line scope}|{sha256-prefix}|{date}

## Cross-Cutting Constraints
|{constraint}:{enforcement}|{one-line description}

## Collections
|decisions|decisions/_index.md|{N} ADRs (strategic + pattern), status-tracked
|episodes|episodes/_index.md|Consolidated patterns from retrospectives

## Active Features (Task-Scoped)
<!-- Entries added when feature starts, removed when shipped -->
<!-- |F-NNN-NNN|status|N/M stories|scope hint|index_path -->

## Recently Completed
<!-- Last 5 features with promoted knowledge links -->

## Tools
|search-index|SEARCH_INDEX.md|Cross-domain concept lookup
```

### MANIFEST Design Decisions

- **Navigation Protocol at top** — tells agents how to navigate the tiered structure
- **Content hash per domain** — agents detect staleness inline during normal navigation
- **Feature-level active entries, not story-level** — saves 100-400 always-loaded tokens
- **Recently Completed** — temporal handoff context for planning agents, capped at 5 entries
- **SEARCH_INDEX.md on-demand** — keyword table costs zero tokens when not needed
- **Overflow fallback** — when Active Features exceeds budget, move detail to `ACTIVE_WORK.md`

---

## 2. Tier 1: Domain Brief Template

**Budget:** 300-800 tokens each. Loaded per-domain.

```markdown
# {Domain Name}

> {One-sentence purpose}

|package|status|aggregates|key ADRs
|`src/{project}/{ctx}/`|{impl/planned}|{list}|{list}

## Mental Model
{2-3 compressed sentences: HOW this domain works and WHY it's shaped this way.
 Not a description — a reasoning framework for edge cases.}

## Invariants
- {Hard constraint — use "must", "never", "always"}

## Key Patterns
|pattern|reference|when to use
|{name}|{path to ref doc}|{one-line trigger}

## Integration Points
|direction|context|mechanism
|Provides → {ctx}|{facade/event/API}
|Consumes ← {ctx}|{facade/event/API}

## Active Work
|feature|status|index
|{F-ref title}|{N/M}|{path to feature-architecture/_index.md}

## Reference Index
|name|path|load when
|{ref name}|{Tier 2 doc path}|{trigger condition}

## Keywords
{comma-separated: synonyms, abbreviations, adjacent concepts}
```

### Brief Authoring Constraints

1. **Always compress from Tier 2, never iterate on Tier 1.** When updating a BRIEF, re-read the relevant Tier 2 references and re-derive the BRIEF from scratch. Never edit a BRIEF by summarizing the previous BRIEF — this causes progressive information loss (context collapse).

2. **Validate via edge-case testing.** A BRIEF is adequate when an agent can resolve domain-specific edge cases using only MANIFEST.md + that BRIEF (Tier 0+1), without needing Tier 2. Test by posing 3 edge-case questions; if the agent must fall through to Tier 2 for >1, the BRIEF is under-specified.

3. **Token budgets enforced per artifact:** per-BRIEF 300-800 tokens; MANIFEST ≤2,000 tokens.

---

## 3. Tier 2: Reference Standards

Tier 2 files are deep references loaded on-demand.

1. **Discoverable from Tier 0 or Tier 1.** Every Tier 2 file must be reachable via MANIFEST → BRIEF → Reference Index. Orphan Tier 2 files should be detected by validation scripts.

2. **Decision-oriented headings.** Use `## When to Use Two-Tier Validation` not `## Validation Overview`.

3. **TOC required for files >5,000 tokens.** Long references must have a table of contents at top so agents can identify relevant sections without reading the full file.

4. **Single-concern scoping.** One reference file = one concept. If a file covers multiple unrelated concerns, split it.

5. **Format selection per content type:**

| Information Type | Preferred Format | Avoid | Token Savings vs Prose |
| ---------------- | ---------------- | ----- | ---------------------- |
| Relationships / dependencies | Mermaid diagram or adjacency table | Prose paragraphs | 40-60% |
| Properties / attributes | Pipe-delimited table or YAML | Prose sentences | 50-70% |
| Enumerations / lists | Markdown list or table | Prose with inline enumerations | 30-50% |
| Procedures with branching | Numbered steps with conditions | Long-form narrative | 20-40% |
| Rationale / tradeoffs | Prose (this is where prose belongs) | Tables or bullet points | — |
| API contracts / schemas | YAML or compact table | Prose descriptions | 50-70% |
| State machines / workflows | Mermaid stateDiagram or flowchart | Prose describing transitions | 40-60% |
| Configuration / settings | YAML or key-value pairs | JSON (20-35% more tokens) | 30-50% |

### Tier 2 Co-location Strategy

Co-locate single-domain refs into `domains/{name}/references/`. Multi-domain refs stay in a shared `reference/` directory with paths from each relevant brief.

---

## 4. Feature Artifact Decomposition

Monolithic planning artifacts become indexed folders with individually-loadable leaves. This is where the **highest token savings** occur (60-85% per agent read).

### Before → After

```text
# BEFORE (monolithic)
feature-name/
├── feature-architecture.md          (2,000+ lines — loaded in full by every agent)
├── feature-code-briefing.md
├── feature-test-strategy.md
└── stories/

# AFTER (atomic indexed)
feature-name/
├── feature-architecture/
│   ├── _index.md                    (~80 lines — summary, decisions, Agent Loading Guide)
│   ├── shared/
│   │   ├── domain.md                (~200 lines — value objects, events, aggregate changes)
│   │   ├── services.md              (~200 lines — application services, adapters)
│   │   └── infrastructure.md        (~200 lines — migrations, package structure, configs)
│   ├── flows/
│   │   └── {flow-name}.md           (~100-200 lines — one end-to-end flow)
│   ├── decisions/
│   │   └── DD-NNN-{slug}.md         (~30-80 lines — one decision with rationale)
│   └── stories/
│       └── S-NNN.md                 (~150-280 lines — story-specific arch delta)
│
├── feature-code-briefing/
│   ├── _index.md                    (~60 lines — file tree, risk summary, symbol counts)
│   ├── risk-assessment.md           (~100 lines — standalone risk analysis)
│   └── stories/
│       └── S-NNN.md                 (~100-200 lines — story symbol inventory)
│
├── feature-test-strategy/
│   ├── _index.md                    (~50 lines — approach, coverage targets)
│   ├── shared-fixtures.md           (~100 lines — shared test factories, helpers)
│   └── stories/
│       └── S-NNN.md                 (~250-350 lines — story test suite spec)
│
└── stories/
    ├── story.yaml
    ├── prd.md
    ├── dev-plan.md
    └── ...
```

### Feature Architecture `_index.md` Template

```markdown
# F-{ref}: {Title}

> **Context:** {BC} | **Status:** {N}/{M} stories

## Summary
{2-3 sentence executive summary}

## Key Decisions
|id|decision|rationale file
|DD-001|{one-line}|[decisions/DD-001-slug.md](decisions/DD-001-slug.md)

## Shared Architecture (load selectively based on task)
|document|scope|lines
|[shared/domain.md](shared/domain.md)|Value objects, events, aggregate changes|~200
|[shared/services.md](shared/services.md)|Application services, adapters|~200
|[shared/infrastructure.md](shared/infrastructure.md)|Migrations, package structure, configs|~200

## Data Flows
|flow|document|lines
|{flow name}|[flows/{slug}.md](flows/{slug}.md)|~150

## Story Deltas (load ONLY your active story)
|story|title|status|delta
|S-{ref}-001|{title}|done|[stories/S-{ref}-001.md](stories/S-{ref}-001.md)

## Agent Loading Guide
|agent|always load|load per task|skip
|story-implementer|_index + story delta|shared/{relevant layer}|other stories, flows, decisions
|architecture-designer|_index + all shared/*|flows/* + decisions/*|stories (except target)
|test-planner|_index + story delta|—|shared/*, flows/*, decisions/*
|dev-planner|_index + story delta|shared/services|shared/infrastructure, flows
|pr-reviewer|_index + story delta|decisions/* (verify compliance)|shared/*, flows/*
```

---

## 5. Leaf Artifact Design

### Single-Concept Leaf Principle

**Every loadable leaf file = one concept. Collections navigated via index files, never loaded whole.**

### Size Targets

| Level | Target Size | Tokens | Purpose |
| ----- | ----------- | ------ | ------- |
| Index (`_index.md`) | 40-80 lines | 400-800 | Navigation: lists all items with one-line descriptions + paths |
| Leaf artifact | 100-400 lines | 800-3,000 | Content: one coherent concern, independently consumable |
| Micro-leaf | 30-80 lines | 200-600 | Atomic reference: single pattern, decision, or component spec |

**Decomposition trigger:** If a leaf exceeds ~400 lines, it likely contains multiple independent concerns. If <30 lines, merge with related content.

### Decomposition Rules by Content Type

| Content Type | Leaf Unit | Size | Rationale |
| ------------ | --------- | ---- | --------- |
| **Component specs** | One component per file | 80-200 lines | Implementer needs only the component they're building |
| **Patterns** | One pattern per file | 100-300 lines | Individual pattern files enable selective loading |
| **Design decisions** | One decision per file | 30-80 lines | Reviewers check specific decisions, not all of them |
| **Events** | All events in one file | 50-150 lines | Events are small and cross-cutting; grouping aids discovery |
| **Test suites** | Per-story test spec | 200-350 lines | Test planner works one story at a time |
| **Data flows** | One flow per file | 100-200 lines | Flows are independently meaningful |

---

## 6. Lifecycle Management

### Archetype Mapping

| Archetype | Content | Location | Lifecycle |
| --------- | ------- | -------- | --------- |
| **Cumulative** | Architecture docs, domain profiles, research | `_kb/reference/`, `research/` | Grows monotonically |
| **Task-Scoped** | Feature planning artifacts | Backlog folders (indexed format) | Created at plan-feature; archived on completion |
| **Decision** | ADRs | `_kb/decisions/` | Created when decided; superseded never deleted |
| **Living** | MANIFEST.md, domain briefs | `_kb/` root + briefs | Updated when state changes |
| **Episodic** | Retrospectives, enrichment reports | `_kb/episodes/` | Created at feature completion; insights consolidated |
