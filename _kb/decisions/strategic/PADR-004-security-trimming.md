<!-- Derived from {Project} PADR-004-security-trimming -->
# PADR-004: Security Trimming and Access Control Model

**Status:** Draft
**Date:** 2025-01-17
**Deciders:** Architecture Team
**Categories:** Strategic, Security

---

## Context

{Project} manages enterprise knowledge with strict security requirements:

- **Multi-tenancy:** Complete isolation between organizational tenants
- **Document-level ACL:** Each piece of content has distinct permissions
- **Inherited permissions:** Content inherits ACL from source documents
- **Query-time filtering:** Search results must be security-trimmed
- **Performance:** Sub-200ms retrieval latency targets

The security model must support:

- Users with multiple group memberships
- Dynamic group changes
- Hierarchical permission inheritance (blocks → content)
- Tiered visibility (existence vs. attributes vs. relationships)

## Decision

**We will implement a hybrid security model combining:**

1. **Denormalized ACL principals** for fast query-time filtering
2. **ReBAC via SpiceDB** for complex hierarchical permission checks
3. **Tiered visibility** for graduated access control

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   SECURITY LAYER                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐     ┌─────────────────┐               │
│  │ Tenant Context  │     │ Principal Cache │               │
│  │   Middleware    │────▶│    (Redis)      │               │
│  └────────┬────────┘     └─────────────────┘               │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────────────────────────────┐               │
│  │        Security Trimming Service         │               │
│  │  ┌─────────────┐   ┌─────────────────┐  │               │
│  │  │ Pre-Filter  │ + │  Post-Filter    │  │               │
│  │  │ (Principal  │   │  (SpiceDB for   │  │               │
│  │  │  arrays)    │   │   hierarchies)  │  │               │
│  │  └─────────────┘   └─────────────────┘  │               │
│  └─────────────────────────────────────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Denormalized ACL Storage

Every searchable content item stores its ACL principals:

```sql
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    content TEXT,
    embedding vector(1024),
    tenant_id TEXT NOT NULL,
    acl_principals TEXT[],  -- ["user:alice", "group:engineering"]
    source_document_id UUID
);

CREATE INDEX idx_chunks_acl ON chunks USING GIN (acl_principals);
```

### SpiceDB Schema (ReBAC)

```zed
definition user {}

definition tenant {
    relation member: user
    relation admin: user
}

definition group {
    relation member: user | group#member
}

definition resource {
    relation tenant: tenant
    relation owner: user
    relation editor: user | group#member
    relation viewer: user | group#member
    relation participant: user | group#member

    permission admin = owner + tenant->admin
    permission write = editor + admin
    permission read = viewer + participant + write
    permission add_content = participant + write
}

definition source_document {
    relation tenant: tenant
    relation owner: user
    relation viewer: user | group#member

    permission view = viewer + owner + tenant->admin
    permission manage = owner + tenant->admin
}

definition Segment {
    relation source_document: source_document
    relation parent_block: resource

    permission view = source_document->view + parent_block->read
}
```

## Rationale

### Why Hybrid Approach?

| Approach | Strengths | Weaknesses |
|----------|-----------|------------|
| **Pre-filter only** | Fast, simple | Can't handle complex inheritance |
| **SpiceDB only** | Handles all cases | Too slow for bulk filtering |
| **Hybrid** | Fast + flexible | More complex |

**Our choice:** Hybrid provides sub-200ms query latency while supporting complex hierarchies.

### Why Denormalized Principals?

Query-time filtering requires fast ACL checks:

```sql
-- Pre-filter: O(1) with GIN index
SELECT * FROM chunks
WHERE embedding <=> $query_vector < 0.5
  AND acl_principals && $user_principals  -- Array overlap
```

Without denormalization, every result would require a SpiceDB call (network latency × N results).

### Why SpiceDB for Complex Cases?

Some permissions require graph traversal:

- "User can view block → therefore view block's content"
- "User is in group → group has viewer role → can view"

SpiceDB handles these with Zanzibar-style relation expansion.

### Tiered Visibility Model

| Tier | What | Visibility Rule |
|------|------|-----------------|
| 1 | Entity existence | Tenant-wide (unless confidential) |
| 2 | Entity attributes | Per-attribute ACL |
| 3 | Relationships | Union of endpoint ACLs |
| 4 | Chunks/Notes | Inherit from source document |
| 5 | Native Workspace files | Block participant ACL |

## Consequences

### Positive

1. **Fast Query Filtering:** GIN index on principal arrays
2. **Flexible Hierarchies:** SpiceDB for complex inheritance
3. **Tenant Isolation:** Required tenant context on all queries
4. **Audit Capability:** Log all access checks
5. **Graduated Access:** Tiered visibility for nuanced control

### Negative

1. **ACL Sync Complexity:** Must propagate ACL changes to denormalized arrays
2. **Eventual Consistency:** ACL updates take time to propagate
3. **Storage Overhead:** Principal arrays on every row
4. **Dual System:** SpiceDB + database arrays to maintain

### Mitigations

| Risk | Mitigation |
|------|------------|
| ACL sync complexity | Event-driven propagation with idempotent handlers |
| Eventual consistency | Document model; critical paths use SpiceDB |
| Storage overhead | Acceptable trade-off for query performance |
| Dual system | Clear boundaries: pre-filter vs. complex checks |

## Implementation

### Principal Resolution

```python
class PrincipalResolver:
    def __init__(self, cache: Redis, user_repo: UserRepository):
        self._cache = cache
        self._user_repo = user_repo

    async def resolve(self, user_id: str) -> list[str]:
        """Resolve all principals for a user."""
        cache_key = f"principals:{user_id}"

        # Check cache
        cached = await self._cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # Build principal list
        user = await self._user_repo.get(user_id)
        principals = [f"user:{user_id}", f"tenant:{user.tenant_id}"]

        # Add group memberships
        groups = await self._user_repo.get_groups(user_id)
        principals.extend([f"group:{g}" for g in groups])

        # Add nested group memberships
        nested = await self._expand_nested_groups(groups)
        principals.extend([f"group:{g}" for g in nested])

        # Cache for 5 minutes
        await self._cache.setex(cache_key, 300, json.dumps(principals))

        return principals

    async def invalidate(self, user_id: str):
        """Invalidate when user's groups change."""
        await self._cache.delete(f"principals:{user_id}")
```

### Security Trimming Service

```python
class SecurityTrimmingService:
    def __init__(
        self,
        principal_resolver: PrincipalResolver,
        spicedb_client: SpiceDBClient
    ):
        self._resolver = principal_resolver
        self._spicedb = spicedb_client

    async def filter_search_results(
        self,
        results: list[SearchResult],
        user_id: str
    ) -> list[SearchResult]:
        """Filter results to only those user can access."""
        principals = await self._resolver.resolve(user_id)

        # Pre-filter already done in query (acl_principals && $principals)
        # Post-filter for edge cases requiring SpiceDB

        if not self._needs_spicedb_check(results):
            return results

        # Batch SpiceDB check
        accessible_ids = await self._batch_spicedb_check(
            user_id, [r.id for r in results]
        )

        return [r for r in results if r.id in accessible_ids]

    def _needs_spicedb_check(self, results: list[SearchResult]) -> bool:
        """Check if any result requires hierarchical permission check."""
        return any(r.has_block_inheritance for r in results)
```

### ACL Propagation

```python
@event_handler(SourceDocumentACLUpdated)
async def propagate_acl_update(event: SourceDocumentACLUpdated):
    """Propagate ACL changes from source to derived content."""
    new_principals = await resolve_document_principals(event.document_id)

    # Update all chunks from this source
    await db.execute("""
        UPDATE chunks
        SET acl_principals = $1
        WHERE source_document_id = $2
    """, new_principals, event.document_id)

    # Update atomic notes
    await db.execute("""
        UPDATE atomic_notes
        SET acl_principals = $1
        WHERE source_document_id = $2
    """, new_principals, event.document_id)

    # Invalidate related caches
    await cache.delete_pattern(f"acl:doc:{event.document_id}:*")
```

### Query with Security Trimming

```python
class SecureHybridRetriever:
    async def retrieve(
        self,
        query: str,
        user_id: str,
        limit: int = 20
    ) -> list[SearchResult]:
        # Resolve user principals
        principals = await self._resolver.resolve(user_id)
        tenant_id = self._extract_tenant(principals)

        # Pre-filtered search (ACL in WHERE clause)
        results = await self._hybrid_search(
            query=query,
            tenant_id=tenant_id,
            principals=principals,
            limit=limit * 2  # Oversample for post-filter
        )

        # Post-filter for complex cases
        filtered = await self._security_trimmer.filter_search_results(
            results, user_id
        )

        return filtered[:limit]

    async def _hybrid_search(
        self,
        query: str,
        tenant_id: str,
        principals: list[str],
        limit: int
    ) -> list[SearchResult]:
        return await self._db.fetch("""
            SELECT id, content, embedding <=> $1 as distance
            FROM chunks
            WHERE tenant_id = $2
              AND acl_principals && $3
            ORDER BY distance
            LIMIT $4
        """, query_embedding, tenant_id, principals, limit)
```

### Tenant Isolation Middleware

```python
class TenantMiddleware:
    async def __call__(self, request: Request, call_next):
        # Extract tenant from JWT
        token = request.headers.get("Authorization")
        claims = decode_jwt(token)
        tenant_id = claims.get("tenant_id")

        if not tenant_id:
            raise HTTPException(401, "Tenant not identified")

        # Set tenant context for request
        request.state.tenant_id = tenant_id
        set_current_tenant(tenant_id)

        response = await call_next(request)
        return response
```

### Row-Level Security (PostgreSQL)

```sql
-- Enable RLS on sensitive tables
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;

-- Tenant isolation policy
CREATE POLICY tenant_isolation ON chunks
    USING (tenant_id = current_setting('app.tenant_id')::text);

-- ACL access policy
CREATE POLICY acl_access ON chunks
    USING (
        acl_principals && string_to_array(
            current_setting('app.user_principals'),
            ','
        )::text[]
    );
```

## Audit Logging

```python
class SecurityAuditLogger:
    async def log_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        granted: bool,
        reason: str
    ):
        entry = AccessLogEntry(
            timestamp=datetime.now(UTC),
            user_id=user_id,
            tenant_id=get_current_tenant(),
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            granted=granted,
            reason=reason
        )
        await self._audit_store.append(entry)
```

## Related Decisions

- PADR-001: Event Sourcing (ACL changes are events)
- ADR-004: graph database (relationship ACLs)

## References

- [Google Zanzibar Paper](https://research.google/pubs/pub48190/)
- [SpiceDB Documentation](https://authzed.com/docs)
- [Azure AI Search Security Trimming](https://learn.microsoft.com/en-us/azure/search/search-security-trimming-for-azure-search)
- Research: `security-models.md`

## Changelog

### 2026-02-05: Terminology Alignment (F-100-004)

- Updated Tiered Visibility table: "Native WM files" changed to "Native Workspace files"
- Core decision unchanged; status remains Draft
