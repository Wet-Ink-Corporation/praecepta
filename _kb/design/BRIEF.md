# Development Process Design

Governance, workflow patterns, and agent pipeline architecture for praecepta-based projects.

## Mental Model

Agent-orchestrated development using tiered context architecture. Agents navigate a MANIFEST → domain briefs → deep references hierarchy, loading only the tokens needed for each task. Constitutional governance enforces immutable principles (async-first, test-first, multi-tenancy). Workflow complexity routes stories through quick/standard/complex paths.

## Key Patterns

- **Tiered context:** MANIFEST (Tier 0) → BRIEF (Tier 1) → references (Tier 2)
- **Constitutional governance:** Immutable development principles enforced via pre-implementation gates
- **Phase transition protocol:** Context compaction at workflow boundaries
- **Standards discovery:** Extract patterns from existing codebase before first story in new domain
- **Delta-based evolution:** ADDED/MODIFIED/REMOVED format for spec changes
- **Token efficiency:** YAML + Markdown over JSON/XML; progressive disclosure

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `references/tiered-context-guideline.md` | Designing information architecture for AI agents |
| `references/tiered-knowledge-architecture.md` | Implementing KB templates (MANIFEST, BRIEF, features) |
| `references/con-development-constitution.md` | Reviewing or enforcing development principles |
| `references/workflow-evolution-spec.md` | Improving agent orchestration workflows |
| `references/proc-when-stuck-protocol.md` | Agent is stuck or blocked |
| `references/agent-skill-design-guidelines.md` | Creating or updating agent skills |
