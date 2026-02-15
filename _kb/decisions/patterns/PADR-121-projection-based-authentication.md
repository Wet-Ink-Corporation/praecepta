<!-- Derived from {Project} PADR-121-projection-based-authentication -->
# PADR-121: Projection-Based Authentication (No Aggregate Hydration)

**Status:** Proposed
**Date:** 2026-02-08
**Context:** F-102-004 Agent Identity (S-102-004-003)
**Domain:** security, event-store-cqrs
**Type:** Pattern Decision

---

## Context

In event-sourced systems, aggregates are hydrated by replaying all events from the event stream (O(n) events). For authentication lookups that happen on **every request**, this creates performance and security challenges:

**Problem 1: Performance**
- Aggregate hydration: Load 100-1000 events from event store (~10-150ms)
- Authentication must be fast (< 1ms for O(1) indexed lookup)
- At 10,000 req/sec, aggregate-based auth = 100-1500 seconds of CPU time per second (impossible)

**Problem 2: DoS Vulnerability**
- Failed auth attempts trigger millions of requests (brute-force, DDoS)
- Each failed auth = full aggregate hydration (expensive operation)
- Attacker can exhaust memory/CPU by spamming invalid credentials

**Problem 3: Coupling**
- Auth middleware would depend on domain aggregate internals (violates hexagonal architecture)
- Aggregate changes (new events, state machine changes) break auth middleware

**Prior art:**
- F-102-003 JIT User Provisioning uses `OidcSubRegistry` projection for fast-path lookup (same pattern)
- F-102-001 JWT auth uses JWKS cache (no aggregate hydration)
- Design decision DD-F4-4 chose projection-based auth for API keys

**Design alternatives considered:**
1. **Aggregate hydration for auth** — Load Agent aggregate, extract key_hash, verify bcrypt
2. **Cache aggregates in-memory** — Hydrate once, cache for TTL (invalidation complexity)
3. **Snapshot-based auth** — Store aggregate snapshots, load snapshot instead of events
4. **Projection-based auth** — Materialized read model updated synchronously with events

---

## Decision

**Authentication lookups (API key validation, session verification) MUST use projection tables, NOT aggregate hydration.**

**Projection requirements:**
1. **Synchronous updates** (PADR-109) — Projections update in same transaction as event storage (no eventual consistency gap)
2. **RLS bypass for auth** — Auth middleware uses superuser connection (runs before tenant context is set)
3. **Indexed lookups** — Projection table has PRIMARY KEY or UNIQUE index on lookup field (key_id, session_id)
4. **Minimal data** — Projection stores ONLY fields needed for auth (key_hash, tenant_id, status), NOT full domain state

**Implementation pattern:**

```sql
-- Projection table (auth-optimized schema)
CREATE TABLE agent_api_key_registry (
    key_id VARCHAR(8) PRIMARY KEY,      -- O(1) indexed lookup
    agent_id UUID NOT NULL,             -- Owner reference
    tenant_id VARCHAR(63) NOT NULL,     -- Tenant boundary
    key_hash TEXT NOT NULL,             -- bcrypt hash (60 chars)
    status VARCHAR(20) NOT NULL,        -- 'active' | 'revoked'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);
```

```python
# Projection update (synchronous, PADR-109)
class AgentAPIKeyProjection(BaseProjection):
    def _handle_issued(self, event: DomainEvent) -> None:
        """UPSERT API key on issuance (idempotent for replay)."""
        self._repo.upsert(
            key_id=event.key_id,
            agent_id=event.originator_id,
            tenant_id=event.tenant_id,
            key_hash=event.key_hash,
            status="active",
        )

# Auth middleware lookup (O(1) indexed SELECT)
async def dispatch(self, request: Request, call_next: Callable) -> Response:
    key_id = extract_key_id(request.headers.get("X-API-Key"))
    key_record = repo.lookup_by_key_id(key_id)  # Projection lookup

    if key_record is None or key_record.status != "active":
        return 401  # Fail fast

    is_valid = bcrypt.checkpw(secret, key_record.key_hash)
    if not is_valid:
        return 401

    # ... set principal context ...
```

**Aggregate is NEVER loaded during authentication.**

---

## Rationale

**Why projection-based (not aggregate hydration)?**
1. **Performance:** O(1) indexed SELECT (~0.1ms) vs O(n) event replay (~10-150ms for 100-1000 events)
2. **DoS resistance:** Failed auth = fast SELECT (no aggregate loading, no memory exhaustion)
3. **Separation of concerns:** Auth infrastructure does not depend on domain aggregate internals
4. **Scalability:** Constant-time lookup scales to millions of requests per second

**Why synchronous projection updates (PADR-109)?**
- **Consistency:** No eventual consistency gap (when `app.save(agent)` returns, projection is updated)
- **Reliability:** Failed projection update = failed event save (atomic transaction)
- **Simplicity:** No background workers, no retry logic, no distributed transactions

**Why RLS bypass for auth?**
- **Timing:** Auth middleware runs BEFORE `TenantStateMiddleware` sets `app.current_tenant`
- **Without bypass:** RLS would block all rows (tenant context not yet set)
- **Security:** Lookup is read-only; tenant isolation is enforced AFTER principal context is set

---

## Consequences

### Positive

1. **O(1) performance** — Auth lookup is constant-time (indexed PRIMARY KEY SELECT)
2. **DoS-resistant** — Failed auth attempts do not trigger expensive aggregate loading
3. **Decoupled** — Auth middleware does not depend on domain aggregate structure
4. **Scalable** — Constant-time lookup scales linearly with request volume
5. **Consistent** — Synchronous projection updates (no stale data)

### Negative

1. **Additional storage** — Projection table duplicates data from event stream (acceptable trade-off)
2. **Synchronous overhead** — Projection updates run in same transaction as event save (~0.5-1ms added latency)
3. **RLS bypass needed** — Auth queries bypass row-level security (mitigated by read-only access)
4. **Limited state visibility** — Projection stores only auth-relevant fields, not full domain state

### Neutral

1. **Projection must be idempotent** — UPSERT pattern for replay-safe updates (standard CQRS pattern)
2. **Schema changes require migration** — Projection table schema is denormalized from aggregate state

---

## Trade-off: Agent Status Not Checked

**Current implementation:** Projection table stores `key_status` (active/revoked), NOT `agent_status` (active/suspended).

**Implication:** Suspending an agent does NOT automatically invalidate their API keys. Keys remain valid until explicitly revoked.

**Why accept this trade-off?**
1. **Projection complexity:** Storing agent_status requires subscribing to `Agent.Suspended` / `Agent.Reactivated` events
2. **Domain separation:** API keys have independent lifecycle from agent lifecycle
3. **Explicit revocation preferred:** Suspending an agent is a logical state change; revoking keys is a security action

**Mitigation options (future enhancements):**
1. **Accept trade-off** (current) — Suspending agent is separate from revoking keys
2. **Add agent_status column** — Projection subscribes to `Agent.Suspended` event, auth checks both `key_status` and `agent_status`
3. **Auto-revoke on suspension** — `Agent.request_suspend()` emits `Agent.AllKeysRevoked` event (domain-level coupling)

**Chosen approach (F-102-004):** Option 1 (accept trade-off). Suspending an agent is rare; revoking keys is an explicit security action. Auto-revocation can be added in future if needed.

---

## Alternatives Considered

### Alternative 1: Aggregate Hydration for Auth

```python
async def dispatch(self, request: Request, call_next: Callable) -> Response:
    key_id = extract_key_id(request.headers.get("X-API-Key"))

    # Load Agent aggregate from event store
    agent = agent_app.repository.get(agent_id)  # O(n) events

    # Find matching key in aggregate state
    key = next((k for k in agent.active_keys if k["key_id"] == key_id), None)
    if key is None or key["status"] != "active":
        return 401

    # Verify bcrypt hash
    is_valid = bcrypt.checkpw(secret, key["key_hash"])
    if not is_valid:
        return 401
```

**Performance:** ~10-150ms per auth (vs ~0.1ms projection lookup)

**Rejected because:**
- 100x slower than projection lookup (10-150ms vs 0.1ms)
- DoS vector (millions of failed auth = millions of aggregate hydrations)
- Couples auth to aggregate structure (domain changes break auth)

---

### Alternative 2: Cache Aggregates In-Memory

```python
# Cache aggregates in-memory with TTL
_agent_cache: dict[UUID, Agent] = {}

async def dispatch(self, request: Request, call_next: Callable) -> Response:
    agent_id = lookup_agent_by_key_id(key_id)  # Still need projection for key_id -> agent_id mapping

    # Check cache
    if agent_id in _agent_cache:
        agent = _agent_cache[agent_id]
    else:
        agent = agent_app.repository.get(agent_id)  # Cache miss -> hydrate
        _agent_cache[agent_id] = agent

    # ... validate key from cached aggregate ...
```

**Rejected because:**
- Still need projection for key_id -> agent_id mapping (cache doesn't solve lookup problem)
- Memory overhead (100,000 agents × 10 KB each = 1 GB RAM)
- Invalidation complexity (event propagation to cache, race conditions)
- Cache miss penalty (O(n) hydration on first request or TTL expiry)

---

### Alternative 3: Snapshot-Based Auth

```python
# Use aggregate snapshots instead of full event replay
async def dispatch(self, request: Request, call_next: Callable) -> Response:
    agent_id = lookup_agent_by_key_id(key_id)

    # Load snapshot (most recent state)
    agent = agent_app.repository.get_snapshot(agent_id)  # Faster than full hydration

    # ... validate key from snapshot ...
```

**Rejected because:**
- Snapshots are for performance optimization, NOT consistency guarantees
- Snapshot may be stale (events saved since last snapshot)
- Still need projection for key_id -> agent_id mapping
- Couples auth to aggregate internals (domain changes break auth)

---

## Implementation Notes

### Projection Table Requirements

**Schema design:**
1. **Indexed lookup field** — PRIMARY KEY or UNIQUE index on lookup field (key_id, session_id)
2. **Minimal columns** — Only fields needed for auth (key_hash, tenant_id, status)
3. **RLS policy** — Row-level security for tenant isolation (bypassed for auth)

From `migrations/versions/20260209_0329_9321c29d2ec5_create_agent_api_key_registry.py`:

```sql
CREATE TABLE agent_api_key_registry (
    key_id VARCHAR(8) PRIMARY KEY,      -- O(1) indexed lookup
    agent_id UUID NOT NULL,
    tenant_id VARCHAR(63) NOT NULL,
    key_hash TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMP WITH TIME ZONE
);

-- RLS for tenant isolation (bypassed for auth, enforced for management queries)
ALTER TABLE agent_api_key_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_api_key_registry FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_agent_api_key_registry
    ON agent_api_key_registry
    USING (tenant_id = current_setting('app.current_tenant', true));
```

---

### Synchronous Projection Updates (PADR-109)

**Guarantee:** Projections update in same transaction as event storage. When `app.save(agent)` returns, projection table is already updated.

From `src/{Project}/shared/infrastructure/projections/agent_api_key.py`:

```python
class AgentAPIKeyProjection(BaseProjection):
    """Materializes Agent API key events into agent_api_key_registry projection table."""

    topics: ClassVar[tuple[str, ...]] = (
        "{Project}.shared.domain.agent:Agent.APIKeyIssued",
        "{Project}.shared.domain.agent:Agent.APIKeyRotated",
    )

    def _handle_issued(self, event: DomainEvent) -> None:
        """UPSERT API key on issuance (idempotent for replay)."""
        self._repo.upsert(
            key_id=event.key_id,
            agent_id=event.originator_id,
            tenant_id=event.tenant_id,
            key_hash=event.key_hash,
            status="active",
        )
```

**Atomicity:** If projection update fails, event save is rolled back (same transaction).

---

### RLS Bypass for Auth Lookups

**Why bypass?** Auth middleware runs BEFORE `TenantStateMiddleware` sets `app.current_tenant` session variable. Without tenant context, RLS would block all rows.

**How?** Auth repository uses **superuser database connection** (bypasses RLS):

From `src/{Project}/shared/infrastructure/agent_api_key_repository.py`:

```python
class AgentAPIKeyRepository:
    def lookup_by_key_id(self, key_id: str) -> AgentAPIKeyRow | None:
        """Look up API key record by key_id for authentication.

        This query runs WITHOUT RLS enforcement (middleware connection
        bypasses tenant context). Returns None if key not found.
        """
        with self._session_factory() as session:
            result = session.execute(
                text("""
                    SELECT key_id, agent_id, tenant_id, key_hash, status
                    FROM agent_api_key_registry
                    WHERE key_id = :key_id
                """),
                {"key_id": key_id},
            )
            # ... return row or None ...
```

**Security:** Lookup is **read-only** (no writes). Tenant isolation is enforced AFTER principal context is set (downstream handlers respect RLS).

---

## Related Decisions

- [PADR-109 Sync-First Eventsourcing](PADR-109-sync-first-eventsourcing.md) — Synchronous projection updates
- [PADR-115 PostgreSQL RLS](PADR-115-postgresql-rls-tenant-isolation.md) — Row-level security for tenant isolation
- [PADR-118 JIT User Provisioning](PADR-118-jit-user-provisioning.md) — Similar projection-based lookup pattern (OidcSubRegistry)
- [PADR-120 Multi-Auth Middleware Sequencing](PADR-120-multi-auth-middleware-sequencing.md) — API key authentication flow

---

## References

- Feature: F-102-004 Agent Identity (S-102-004-003)
- Pattern: [ref-infra-projection-based-auth.md](../../domains/security/references/ref-infra-projection-based-auth.md)
- Pattern: [ref-infra-jit-provisioning.md](../../domains/security/references/ref-infra-jit-provisioning.md) (similar fast-path lookup)
- Implementation: `src/{Project}/shared/infrastructure/projections/agent_api_key.py`
- Implementation: `src/{Project}/shared/infrastructure/agent_api_key_repository.py`
- Implementation: `src/{Project}/shared/infrastructure/middleware/api_key_auth.py`

---

**End of ADR**
