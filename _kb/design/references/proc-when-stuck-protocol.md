# When Stuck Protocol

> **Purpose**: Structured approach to resolving blockers without hallucination or workarounds.
> Reference this protocol whenever implementation seems blocked or impossible.

## Step 1: Search Before Asserting

Before claiming any capability is "impossible" or "unavailable":

```bash
# Search for existing patterns
rg "similar_pattern" src/
rg "error_message" --type py

# Search for prior implementations
rg "class.*Repository" src/ -A 10
rg "async def.*handler" src/ -A 10
```

**Document what you searched for and found (or didn't find).**

## Step 2: Consult Documentation

Check these locations in order:

1. **ADRs**: `_kb/decisions/` - Prior architectural decisions
2. **Architecture docs**: `_kb/MANIFEST.md` → domain BRIEFs → references
3. **Skill documentation**: `.windsurf/skills/` or `.claude/skills/`
4. **CLAUDE.md**: Project-level guidance

**Document which docs you consulted and what you learned.**

## Step 3: Verify Constraints

Ask yourself:

- Is this actually impossible, or just unfamiliar?
- Has this been done elsewhere in the codebase?
- Does an ADR explain why a particular approach was chosen?
- Am I trying to do something the architecture explicitly forbids?

**If the architecture forbids it, that's the answer - don't work around it.**

## Step 4: Escalate Clearly

If still stuck after Steps 1-3, report with this format:

```markdown
## BLOCKED

**Issue**: {Clear description of what is blocked}

**Searched**:
- `rg "{pattern1}" src/` - {result}
- `rg "{pattern2}" src/` - {result}

**Consulted**:
- `_kb/decisions/NNN.md` - {what it said}
- `docs/architecture/X.md` - {what it said}

**Constraint Check**:
- This appears to be {impossible / unfamiliar / forbidden by architecture}
- Reason: {explanation}

**Question for Human**:
{Specific question that would unblock progress}

**Options** (if any):
1. {Option A} - {tradeoffs}
2. {Option B} - {tradeoffs}
```

---

## FORBIDDEN Actions

When stuck, you MUST NOT:

- ❌ Claim something is "impossible" without search evidence
- ❌ Invent workarounds that violate architecture
- ❌ Skip tests because "testing is hard"
- ❌ Convert async to sync to avoid complexity
- ❌ Ignore tenant_id requirements
- ❌ Create mock implementations instead of real ones
- ❌ Proceed without understanding the pattern

---

## Common Stuck Scenarios

### "I can't find how to do X"

**Solution**: Search for analogous implementations:

```bash
rg "similar_feature" src/ -l
```

Then read those files for patterns.

### "The test setup is too complex"

**Solution**: Read `tests/conftest.py` for existing fixtures.
TestContainers setup is already done - use it.

### "Async is confusing"

**Solution**:

- Read PADR-109 on sync-first event sourcing / async strategy
- Find existing async implementations and copy the pattern
- Use `@pytest.mark.asyncio` for tests

### "I don't understand the repository pattern"

**Solution**:

- Read existing repository in `packages/*/src/praecepta/`
- Copy the session factory pattern exactly
- Follow the same query construction approach

### "Multi-tenancy is complex"

**Solution**:

- Every query MUST filter by tenant_id
- This is non-negotiable (Constitution Article V)
- Find existing tenant-scoped queries and copy them

---

## After Getting Unstuck

Once the blocker is resolved:

1. Document what solved it in the implementation
2. Consider if this should be added to discovered-patterns.md
3. Update context-brief.md if it affects future phases
4. Add a note to the retrospective for process improvement
