# Workflow Evolution Design Specification

**Status**: Reference
**Source**: Analysis of Spec-Kit, OpenSpec, BMAD-METHOD, Agent OS, Tessl

## Executive Summary

Synthesized "golden thread" principles from five leading spec-driven development frameworks, mapped to improvements for agent-orchestrated development workflows.

---

## Part 1: Framework Analysis

### 1.1 GitHub Spec-Kit

**Core Philosophy**: Specifications don't serve code—code serves specifications.

| Principle | Mechanism | Why It Works |
|-----------|-----------|--------------|
| **Constitutional Governance** | `constitution.md` with immutable articles | Prevents architectural drift by making principles uncheckable gates |
| **Test-First Imperative** | "No implementation code shall be written before unit tests are written, validated, and confirmed to FAIL" | Eliminates TDD violations by making test-first a hard prerequisite |
| **Self-Review Checklists** | Templates include `- [ ]` checklists that agents must complete | Forces systematic self-audit, catches gaps before implementation |
| **Phase Gates** | "Simplicity Gate", "Anti-Abstraction Gate" before implementation | Blocks over-engineering by requiring explicit justification |
| **Research-Driven Context** | Research agents gather library compatibility, performance benchmarks | Prevents hallucination by mandating discovery before assertion |

### 1.2 OpenSpec

**Core Philosophy**: Fluid not rigid, iterative not waterfall, brownfield-first.

| Principle | Mechanism | Why It Works |
|-----------|-----------|--------------|
| **Delta-Based Evolution** | ADDED/MODIFIED/REMOVED format | Makes changes explicit and reviewable |
| **Brownfield-First** | Analyze existing code before writing specs | Prevents reimplementing existing patterns |
| **Iterative Refinement** | Specs evolve through implementation feedback | Avoids "big design up front" waste |

### 1.3 BMAD-METHOD

**Core Philosophy**: Right-sized process based on task complexity.

| Principle | Mechanism | Why It Works |
|-----------|-----------|--------------|
| **Two-Tier Workflow** | Quick Flow vs Full Planning Path | Prevents over-engineering trivial tasks |
| **Quality Checks** | Pre-implementation verification gates | Catches issues before they compound |
| **Interactive Help** | `/bmad-help` command for status and guidance | Reduces context-switching overhead |

### 1.4 Agent OS

**Core Philosophy**: Discover → Deploy → Shape.

| Principle | Mechanism | Why It Works |
|-----------|-----------|--------------|
| **Standards Discovery** | Extract patterns from existing codebase first | Prevents inconsistency with established patterns |
| **Progressive Autonomy** | Discover existing, deploy established, shape new | Scales governance with novelty |

### 1.5 Tessl

**Core Philosophy**: Version-locked context tiles prevent stale knowledge.

| Principle | Mechanism | Why It Works |
|-----------|-----------|--------------|
| **Versioned Context** | Skills declare version compatibility | Prevents applying outdated patterns |
| **Context Tiles** | Independently-loadable knowledge units | Enables precise context loading |

---

## Part 3: Design Patterns (Generic)

### 3.1 Constitution-Based Governance

Create an immutable governing document for all project development:

```markdown
# {Project} Development Constitution

## Article I: Async-First Principle
All I/O operations MUST use asyncio patterns.

## Article II: Test-First Imperative
No implementation code SHALL be written before:
1. Test files are created with failing tests
2. Tests are validated against test-plan.md
3. Tests are confirmed to FAIL (Red phase)

## Article III: Discovery Before Assertion
Before claiming any capability is "impossible" or "unavailable":
1. Search codebase for existing patterns
2. Consult relevant skill documentation
3. Check ADRs for prior decisions

## Article IV: Planning Artifacts Are Binding
architecture-design.md and dev-plan.md are CONTRACTS, not suggestions.

## Article V: Multi-Tenancy Enforcement
Every database query, every API endpoint, every event handler MUST
include tenant_id scoping. There are NO exceptions.

## Article VI: Pattern Consistency
When implementing a new capability, first discover existing patterns.
Deviation requires documented justification.
```

### 3.2 Pre-Implementation Gates

```markdown
## Phase 0: Pre-Implementation Gates

### Gate 1: Constitutional Compliance
- [ ] Async-First: No sync I/O patterns introduced?
- [ ] Test-First: Test files created before implementation?
- [ ] Discovery: Searched codebase before making capability claims?
- [ ] Planning Adherence: Following architecture-design.md exactly?
- [ ] Multi-Tenancy: All queries include tenant_id?
- [ ] Pattern Consistency: Found and applied existing patterns?

### Gate 2: Context Verification
- [ ] Read existing patterns in target domain (list files read)
- [ ] Loaded relevant skills (list skills invoked)
- [ ] Consulted ADRs for prior decisions (list ADRs checked)

### Gate 3: Test-First Verification
- [ ] Test file path: _______________
- [ ] Tests confirmed to FAIL before implementation

**STOP**: Do not proceed to implementation until all gates pass.
```

### 3.3 Standards Discovery Workflow

Extract patterns from existing codebase before first story in a new domain:

1. **Identify domain boundaries** — which directories/modules are relevant
2. **Extract patterns** — API, Repository, Testing, Error handling patterns
3. **Generate standards document** — `discovered-patterns.md` with code examples
4. **Inject into context brief** — append discovered patterns summary

### 3.4 Two-Tier Workflow System

Route stories by complexity:

| Path | Criteria | Workflow |
|------|----------|---------|
| **Quick** | Bug/refactor, ≤2 files, no new deps | PRD (abbreviated) → Dev-plan → Implement → Validate |
| **Standard** | Feature, moderate complexity, single BC | Research → PRD → Architecture → Test-plan → Dev-plan → Implement → Validate → Review |
| **Complex** | Cross-cutting, new BC, external integrations | All standard + Domain research + ADR creation + Architecture review checkpoint |

### 3.5 Interactive Help System

Read current orchestration state and suggest next action:
1. Load state and all existing artifacts
2. Diagnose position (current phase, completed/missing artifacts, blocked gates)
3. Generate guidance with next required action and quick commands

### 3.6 Delta-Based Spec Evolution

For stories that modify existing behavior, use delta format in PRD:

```markdown
### ADDED
#### REQ-001: {New Requirement}
{description}
##### Acceptance Criteria
- AC-001: {criterion}

### MODIFIED
#### REQ-002: {Modified Requirement} (from S-NNN)
~~{original}~~
{updated}

### REMOVED
(none for this story)
```

### 3.7 Versioned Skill Context

Each skill file should state its version scope:

```markdown
# {Library} Skill
**Applies to**: {Library} {version}+ with {feature}
**Last verified**: {date}
```

### 3.8 Self-Review Checklists

Add completion checklists to implementation workflow covering:
- **Code Quality** — type hints, imports, no unjustified `# type: ignore`
- **Test Coverage** — unit, integration, edge cases from test-plan
- **Architecture Compliance** — ports-and-adapters, events for state changes
- **Multi-Tenancy** — tenant_id on all queries, endpoints, DTOs
- **Documentation** — docstrings, ADRs for new decisions

### 3.9 Context Engineering and Phase Transition Protocol

#### Core Principles (from Anthropic)

1. **Smallest Possible High-Signal Context** — find the minimal set of tokens that maximize desired outcome
2. **Structured Note-Taking as Memory** — agents write notes persisted outside the context window
3. **Compaction at Boundaries** — distill context at phase transitions for minimal performance degradation

#### Phase Transition Protocol

| Phase | Load | Do NOT Load |
|-------|------|-------------|
| **Planning** | PRD, architecture, test-plan | Implementation details, test output |
| **Implementation** | dev-plan (current phase), discovered-patterns, target files | Full PRD, research, other phases |
| **Validation** | test-plan, test-report template, implementation files | Planning artifacts |
| **Review** | All summaries, PR template | Raw implementation details |

#### Anti-Conflation Rules (from Manus)

1. **Recite Goals at Context End** — restate current objective after major tool calls
2. **Keep Errors Visible** — leave wrong turns in context to prevent repetition
3. **Avoid Self-Few-Shotting** — introduce variation in repeated operations

### 3.10 Token-Efficient Artifact Structure

| Format | Efficiency vs JSON |
|--------|-------------------|
| JSON | baseline |
| XML | -22% worse |
| YAML | +24% better |
| Markdown | +25% better |

**Key insight**: YAML and Markdown are the most token-efficient formats.

#### The Six Core Areas (from GitHub Study of 2,500+ Agent Files)

| Area | What to Include | Token-Efficient Approach |
|------|-----------------|-------------------------|
| **Commands** | Full executable commands with flags | YAML list, not prose |
| **Testing** | How to run, framework, coverage expectations | Commands + brief notes |
| **Project Structure** | Where source/tests/docs live | Directory tree, not description |
| **Code Style** | One real snippet beats paragraphs | Example code block |
| **Git Workflow** | Branch naming, commit format, PR requirements | Bullet list |
| **Boundaries** | What to never touch | Three-tier table |

#### References

- Anthropic Engineering. "Effective Context Engineering for AI Agents." Sep 2025.
- LangChain Blog. "Context Engineering for Agents." Jul 2025.
- Manus (Meta). "Context Engineering for AI Agents: Lessons from Building Manus." Jul 2025.
- GitHub Blog. "Lessons from 2,500+ agent configs." Jan 2026.
- Addy Osmani. "How to Write a Good Spec for AI Agents." Jan 2026.
