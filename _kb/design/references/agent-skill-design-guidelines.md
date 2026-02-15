# Agent & Skill Design Guidelines

Guidelines for creating agents and skills that follow the layered pattern used by `backlog-researcher` and `prd-author`.

## Core Principle: Layered Context

Effective agents use **three layers** of process documentation:

```
┌─────────────────────────────────────────┐
│  AGENT (.claude/agents/name.md)         │  ← Thin orchestrator (100-150 lines)
│  - Role definition                       │
│  - Tool access                           │
│  - Workflow summary                      │
│  - Error handling overview               │
└─────────────────────────────────────────┘
                    │
                    ▼ delegates to
┌─────────────────────────────────────────┐
│  SKILL (.claude/skills/.../SKILL.md)    │  ← Detailed workflow (200-350 lines)
│  - Full phase descriptions               │
│  - Reference file links                  │
│  - When to use guidance                  │
│  - Output specifications                 │
└─────────────────────────────────────────┘
                    │
                    ▼ loads on-demand
┌─────────────────────────────────────────┐
│  REFERENCES (references/*.md)           │  ← Phase-specific detail (100-250 lines)
│  - Templates                             │
│  - Checklists                            │
│  - Question banks                        │
│  - Tool patterns                         │
└─────────────────────────────────────────┘
```

**Why this works:** LLMs manage context more effectively when process knowledge is layered. Loading 500 lines of instructions at once dilutes attention; loading 100-150 lines of orchestration + pulling in detail for the current phase keeps focus sharp.

## Size Guidelines

Size limits are tiered based on workflow complexity. **Hard caps are enforced.**

### Agent Size Tiers

| Tier | Line Count | Use For | Example |
|------|------------|---------|---------|
| Thin | 80-120 | Simple 3-4 phase workflows, clear delegation | `prd-author` (92 lines) |
| Standard | 120-170 | Complex 5-7 phase workflows, multiple checkpoints | `test-planner`, `code-explorer` |
| **Hard Cap** | **200** | **No agent should exceed this** | Refactor to skill if needed |

### Skill Size Tiers

| Tier | Line Count | Use For | Example |
|------|------------|---------|---------|
| Simple | 200-280 | Straightforward workflows, few decision points | `prd` (204 lines) |
| Standard | 280-380 | Multi-phase workflows with branching | `architecture-design`, `code-briefing` |
| Complex | 380-450 | Deep workflows with many tool integrations | `implement`, `docs-update` |
| **Hard Cap** | **450** | **No skill should exceed this** | Extract tables to references |

### Reference File Limits

| Type | Line Count | Notes |
|------|------------|-------|
| Templates | 150-350 | Longer OK for detailed templates |
| Patterns | 100-200 | Quick-reference.md should be ~150 max |
| Checklists | 100-250 | Tables can be dense |
| Question banks | 150-300 | Comprehensive but scannable |

### When to Extract Content

Extract content from agent/skill to references when:

- Adding tables longer than 10 rows
- Including code examples longer than 15 lines
- Duplicating content that exists in skill references
- Approaching the hard cap for your tier

## Directory Structure

### Agent Location

```
.claude/agents/{agent-name}.md
```

### Skill Location (for project-specific skills)

```
.claude/skills/{domain}/{skill-name}/
├── SKILL.md
├── patterns/
│   └── quick-reference.md
└── references/
    ├── {phase-or-topic-1}.md
    ├── {phase-or-topic-2}.md
    └── {phase-or-topic-3}.md
```

### Naming Conventions

| Component | Convention | Example |
|-----------|------------|---------|
| Agent file | kebab-case | `prd-author.md` |
| Skill directory | kebab-case | `prd/` |
| Skill name | hyphen-separated namespace | `backlog-prd` |
| Reference files | kebab-case, descriptive | `interview-questions.md` |
| Pattern files | kebab-case | `quick-reference.md` |

## Agent Design

### Frontmatter Template

```yaml
---
name: {agent-name}
description: |
  Use this agent when the user asks to "{trigger phrase 1}", "{trigger phrase 2}",
  or when {context trigger}. {Brief description of what agent does}.
trigger: /{command-name}       # Explicit slash command trigger (optional but recommended)
model: sonnet
color: {blue|cyan|green|yellow|orange|red|purple}
tools:
  - Read
  - Write
  - Glob
  - Grep
  - Skill          # Required for skill delegation
  - AskUserQuestion
  # Add domain-specific tools (MCP, etc.)
---
```

**Trigger field:** The optional `trigger` field provides an explicit slash command for invoking the agent. While agents can still be activated via natural language matching on the description, the trigger field improves discoverability and provides certainty of activation.

### Agent Body Structure (80-170 lines)

```markdown
# {Agent Name}

{1-2 sentence role description}

## Process

Load the {skill-name} skill for detailed workflow guidance:

```

Skill: {namespace}:{skill-name}

```

The skill provides:
- {Key capability 1}
- {Key capability 2}
- {Key capability 3}

## Workflow Summary

### Phase 1: {Phase Name}
{2-3 sentences summarizing phase}

Load `references/{file}.md` for {specific guidance}.

### Phase 2: {Phase Name}
{2-3 sentences summarizing phase}

... (repeat for each phase)

## Key Principles

1. **{Principle 1}** - {Brief explanation}
2. **{Principle 2}** - {Brief explanation}
... (3-5 principles)

## Error Handling

**{Error case 1}:**
- {Action}
- {Action}

**{Error case 2}:**
- {Action}

## Output

{Where output goes}

{What completion report includes}
```

### What Belongs in the Agent

| Include | Exclude |
|---------|---------|
| Role definition | Detailed phase instructions |
| Tool list | Template content |
| Workflow overview (1-2 lines/phase) | Full question banks |
| Key principles (3-5 items) | Validation checklists |
| Error handling summary | Tool-specific patterns |
| Output location | Examples longer than 5 lines |

## Skill Design

### SKILL.md Frontmatter

```yaml
---
name: {namespace}:{skill-name}
description: |
  This skill should be used when the user asks to "{trigger 1}", "{trigger 2}",
  or {context trigger}. {What the skill produces}.
arguments:
  - name: {arg_name}
    description: {What it is}. If omitted, {default behavior}.
    required: false
---
```

### SKILL.md Body Structure (200-400 lines)

```markdown
# {Skill Name}

{1-2 sentence description of what this skill creates}

## Purpose

This skill helps create **{artifact}** for {use case}. The output is optimized for {consumer}.

## When to Use

- {Trigger condition 1}
- {Trigger condition 2}
- {Trigger condition 3}

## Workflow Overview

```

1. {PHASE 1 NAME}  → {Brief description}
2. {PHASE 2 NAME}  → {Brief description}
...

```

## Quick Start

Load `patterns/quick-reference.md` for the condensed workflow checklist.

## Detailed Process

### Phase 1: {Phase Name}

**Goal:** {What this phase accomplishes}

**Steps:**
1. {Step}
2. {Step}
...

**Output:** {What to present/produce}

### Phase 2: {Phase Name}
...

(Continue for each phase, linking to reference files where detail is needed)

## Output Location

```

{path/to/output/artifact}

```

## Reference Files

**Load on-demand from `references/`:**

| File | Use When |
|------|----------|
| `{file-1}.md` | {Trigger for loading} |
| `{file-2}.md` | {Trigger for loading} |

**Patterns:**

| File | Use When |
|------|----------|
| `quick-reference.md` | Condensed workflow checklist |

## Error Handling

{Error cases with actions}

## Key Principles

{3-6 principles guiding execution}

## Example Invocation

```

/{skill-name} {example_args}

```

## Related Skills

- **`{related-skill}`** - {Relationship}

## Cross-References

- {Link to related docs}
```

### What Belongs in the Skill

| Include | Exclude |
|---------|---------|
| Full phase descriptions | Exhaustive templates |
| Reference file links | Complete question banks |
| When-to-use guidance | Detailed validation rules |
| Output specifications | Tool call examples |
| Error handling | Long code examples |
| Principles | Checklists |

## Reference File Design

### Types of Reference Files

| Type | Purpose | Example |
|------|---------|---------|
| Templates | Output structure | `prd-template.md` |
| Questions | Interview/elicitation | `interview-questions.md` |
| Patterns | Tool usage patterns | `scope-analysis.md` |
| Checklists | Validation criteria | `quality-checklist.md` |
| Strategies | Decision guidance | `research-strategies.md` |

### Reference File Structure

```markdown
# {Topic Name}

{1-2 sentence description of what this file provides}

## {Section 1}

{Content organized for quick scanning}

## {Section 2}

{Tables, checklists, code blocks as appropriate}

...
```

### Reference File Guidelines

- **Self-contained:** Can be understood without reading other files
- **Scannable:** Use tables, checklists, headers liberally
- **Focused:** One concern per file (~100-200 lines)
- **Actionable:** Provide templates, not just descriptions

## Quick Reference Pattern

Every skill should have `patterns/quick-reference.md`:

```markdown
# {Skill} Quick Reference

Condensed workflow checklist for {task}.

## Pre-Flight Checklist

```

□ {Prerequisite 1}
□ {Prerequisite 2}

```

## Phase 1: {Name}

{Minimal steps as checklist or numbered list}

## Phase 2: {Name}

...

## Error Handling

| Error | Action |
|-------|--------|
| {case} | {action} |

## Abort Conditions

Skip {task} if:
- {Condition}

## Reference Files

| Need | Load |
|------|------|
| {topic} | `references/{file}.md` |
```

## Progressive Disclosure Pattern

### When to Load References

| Situation | Action |
|-----------|--------|
| Starting a phase | Check if reference file needed |
| Uncertain about details | Load relevant reference |
| Need templates | Load template reference |
| Validating output | Load checklist reference |

### How to Reference in SKILL.md

```markdown
### Phase 3: Interview

**Goal:** Gather requirements through targeted questions.

Load `references/interview-questions.md` for the complete question set.

**Section Matrix:**
| Section | Approach |
|---------|----------|
| Overview | Validate |
| User Value | **Ask** |
...
```

The skill provides the matrix overview; the reference file provides the actual questions.

## Anti-Patterns to Avoid

### Monolithic Agent

**Problem:** 500+ line agent with everything inline
**Fix:** Extract to skill + references

### Missing Skill Tool

**Problem:** Agent can't load skill files
**Fix:** Add `Skill` to tools list

### Orphaned References

**Problem:** Reference files exist but skill doesn't link them
**Fix:** Add reference table to SKILL.md

### Duplicate Content

**Problem:** Same content in agent and skill
**Fix:** Agent summarizes, skill details, references elaborate

### Over-Nesting

**Problem:** references/phase1/step2/substep3/...
**Fix:** Keep flat: patterns/ and references/ only

## Checklist for New Agent/Skill

### Agent Checklist

```
□ Frontmatter complete (name, description, model, color, tools)
□ Trigger field present (optional but recommended)
□ Skill tool included if delegating
□ Role description (1-2 sentences)
□ Workflow summary (1-2 lines per phase)
□ Key principles (3-5 items)
□ Error handling summary
□ Output location specified
□ Under 200 lines total (hard cap)
□ Thin agents: 80-120 lines | Standard agents: 120-170 lines
```

### Skill Checklist

```
□ Frontmatter complete (name, description, arguments)
□ Purpose section explains what/why
□ When to Use section with triggers
□ Workflow overview (ASCII diagram)
□ Quick Start points to quick-reference.md
□ Each phase has Goal, Steps, Output
□ Reference file table present
□ Error handling section
□ Example invocation
□ Under 450 lines total (hard cap)
□ Simple: 200-280 lines | Standard: 280-380 lines | Complex: 380-450 lines
```

### Reference Files Checklist

```
□ quick-reference.md exists in patterns/ (target ~150 lines)
□ Each phase with complex detail has reference file
□ Templates extracted to reference files (150-350 lines)
□ Checklists extracted to reference files (100-250 lines)
□ Each file is self-contained
□ Files are scannable (tables, checkboxes, headers)
```

## Pipeline Agent ADO Tag Hygiene

Pipeline agents that add `agent:xxx` tags via `pre_flight.py` MUST remove them on every exit path:

- **Gate pass/fail**: Handled automatically by `post_flight.py` (unconditional tag removal)
- **BLOCK without post-flight**: Agent must call `ado_tag(ref, 'remove', tag)` inline before stopping

The `agent:xxx` tag is **transient** — it signals active work, not failure state. The `blocked` tag is the durable failure signal. See `column-agent-baseline.md` Tag Lifecycle Invariant for the full contract.

## Pipeline Agent Headless Execution Contract

Pipeline agents must work identically whether invoked manually (via `/command`) or headlessly (via `dispatch.py` + `claude -p` from n8n). This is a hard requirement for automated orchestration.

| # | Requirement | Rationale |
|---|------------|-----------|
| 1 | Read ALL context from prompt + filesystem | No conversation history in headless mode |
| 2 | Run pre/post flight via Bash tool | Deterministic scripts, not LLM interpretation |
| 3 | Write completion record to `agent-log/` | Structured output, not stdout |
| 4 | Handle errors autonomously (max 3 retries, then BLOCK) | No human to ask in headless mode |
| 5 | Commit own work artifacts with conventional commits | Agent is responsible for its own git operations |
| 6 | Never use `AskUserQuestion` | Headless mode has no interactive user |

See `column-agent-baseline.md` Headless Execution Contract for the full specification.

## Pipeline Agent Git Operations

Pipeline agents operate in different git contexts depending on which board they serve. Agents receive their working directory from the spawn prompt and should not assume a fixed repo location.

### Git Operations per Column

| Column Type | Working Directory | Worktree? | Commits to | Convention |
|-------------|------------------|-----------|-----------|-----------|
| Feature Board AI columns | Primary repo clone | No | `main` | `docs(bklg): F-NNN-NNN {desc} [agent:{column}]` |
| Story Planning | Story worktree | Yes — dispatch creates | Story branch | `docs(bklg): S-NNN-NNN-NNN {desc} [agent:{column}]` |
| Plan Review | Story worktree | Yes — reuses existing | Story branch | `docs(bklg): S-NNN-NNN-NNN {desc} [agent:{column}]` |
| Backend Dev onwards | Story worktree | Yes — reuses existing | Story branch | Standard conventional commits |
| Docs (post-merge) | Primary repo clone | No | `main` | `docs: {desc} [agent:docs]` |

### Worktree-Aware Agents

When working in a story worktree:

- **Work in the directory given in the prompt.** Don't hardcode or assume a repo root path.
- **Use relative paths** from the working directory root for all file operations.
- **Do not run `git checkout`.** The story branch is already checked out in the worktree. Running `git checkout` would switch branches and break the isolation model.
- **Verify branch state** in pre-flight: check that `git rev-parse --abbrev-ref HEAD` matches `story.yaml.branch`.
- **Agents don't need to know they're in a worktree.** The filesystem looks identical to a regular checkout. The worktree is transparent to the agent's workflow.

### Pipeline Agent Checklist (additions)

```
□ Pre-flight adds agent tag via --agent-tag parameter
□ Post-flight removes agent tag (automatic, both pass and fail)
□ Error handling table references "Tag Cleanup" for every BLOCK scenario
□ Tag Cleanup on BLOCK section present with correct inline ado_tag() call
□ Headless compatible: no AskUserQuestion, no conversation history dependency
□ Git operations match column type (see Git Operations per Column table)
□ Working directory from prompt, not hardcoded paths
□ No git checkout commands (Story Board agents)
□ Conventional commit with [agent:{name}] trailer
```

## Example: Creating a New Agent

**Scenario:** Create a `test-planner` agent that generates test plans.

### Step 1: Create Skill Structure

```
.claude/skills/{project}-backlog/test-plan/
├── SKILL.md
├── patterns/
│   └── quick-reference.md
└── references/
    ├── test-categories.md
    ├── coverage-matrix.md
    └── test-template.md
```

### Step 2: Write SKILL.md (~200 lines)

- Frontmatter with name, description, arguments
- Purpose and When to Use
- 4-phase workflow (Context → Analysis → Planning → Review)
- Reference file links per phase
- Error handling and principles

### Step 3: Write Reference Files

- `test-categories.md`: Unit, integration, e2e definitions
- `coverage-matrix.md`: What to test by story type
- `test-template.md`: Test plan document structure

### Step 4: Write quick-reference.md

- Condensed checklist version of workflow
- Reference file lookup table

### Step 5: Create Agent (~100 lines)

- Frontmatter with Skill in tools
- Role description
- Workflow summary (delegating to skill)
- Error handling summary

### Step 6: Verify

- Agent loads and delegates to skill
- Skill references load on demand
- Quick reference provides fast path
