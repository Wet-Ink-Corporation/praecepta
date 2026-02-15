# Security & Access Control

{Project} implements a tiered visibility model with ACLs inherited from source systems.

## Core Principle

> "Know that it exists, but not necessarily what it connects"

Like a company directory: you know someone exists, but not necessarily their salary.

## Tiered Visibility Model

### Layer 1: Entity Existence (Tenant-Wide Visible)

All authenticated users can see:

- Entity exists (entity_id)
- Entity type (person, org, concept, etc.)
- Canonical name

**Exception:** Entities marked `is_confidential=true` require ACL check.

### Layer 2: Entity Attributes (Source Document ACL)

Extended attributes inherit ACL from source document:

- User queries entity "Jane Smith"
- System returns entity + only attributes user has access to
- Attributes from restricted docs are omitted (not masked)

### Layer 3: Relationships (Source Document ACL)

Relationships inherit ACL from extraction source.

**Multi-source handling (union semantics):**
If "Jane -[manages]-> Bob" appears in:

- Doc A (ACL: HR only)
- Doc B (ACL: All employees)

Result: Two relationship records (different provenance). Query returns if user has access to ANY source.

### Layer 4: Chunks & Notes (Direct Inheritance)

ACL = source document ACL (straightforward inheritance)

### Layer 5: Workspace Native Entries (Block Participants)

Entries created natively in a workspace block inherit ACL from the block's participant list (write/admin roles).

## ACL Implementation

### Storage: Denormalized for Performance

Every item stores:

```
acl_principals: ["u123", "group:engineering", "group:all-staff"]
source_document_id: <for provenance and ACL updates>
```

### Query: Fast Filter

Vector store filter:

```
WHERE acl_principals CONTAINS ANY [user's principals]
```

Graph query filter:

```
WHERE ANY(p IN acl_principals WHERE p IN $user_principals)
```

### Updates: Eventual Consistency

When document ACL changes:

1. Update document's acl_principals
2. Async job propagates to all derived items
3. Changes visible within minutes (eventual consistency)

## Key Design Decisions

| Decision | Resolution | Rationale |
|----------|------------|-----------|
| Entity ACL | Existence open, attributes controlled | Like a directory: you know someone exists, but not their salary |
| Relationship ACL | Source document ACL, union semantics | If visible in any source, relationship is visible |
| Chunk/Note ACL | Direct inheritance from source document | Straightforward, predictable |
| Workspace native entry ACL | Block participants (write/admin) | Entries created in scope inherit scope's access |
| ACL storage | Denormalized on items | Fast query-time filtering; async propagation on change |

---

**Prerequisites:**

- [Memory Types](./memory-types.md) - Content types and their origins
- [Memory Blocks](./memory-blocks.md) - Block participants

**Related:**

- [Procedures: Query Processing](../procedures/query-processing.md) - ACL filtering step
