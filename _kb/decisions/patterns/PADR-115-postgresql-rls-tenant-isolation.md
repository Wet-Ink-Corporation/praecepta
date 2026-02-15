<!-- Derived from {Project} PADR-115-postgresql-rls-tenant-isolation -->
# PADR-115: PostgreSQL RLS for Tenant Isolation

**Status:** Proposed
**Date:** 2026-02-06
**Context:** F-101-002 Database Isolation
**Deciders:** Architecture Team
**Category:** Infrastructure / Security

---

## Context

{Project} is a multi-tenant system where tenant data must be strictly isolated at the database layer. The application uses PostgreSQL for event storage (eventsourcing library) and projections (materialized read models). Without database-layer isolation, application-layer filtering alone presents security risks:

1. **SQL injection bypass:** Malicious input could bypass application filters
2. **Direct database access:** Migrations, admin tools, and debugging queries could accidentally access cross-tenant data
3. **Code-level bugs:** Missing `WHERE tenant_id = :tenant` clauses in queries expose data
4. **Audit complexity:** No centralized enforcement point for tenant isolation

**Question:** How do we enforce tenant data isolation at the database layer in a way that:

- Works transparently with the eventsourcing library (which has no tenant awareness)
- Is safe for connection-pooled environments (no context leakage)
- Supports both sync and async database operations
- Requires minimal changes to application code
- Provides defense-in-depth security guarantees

---

## Decision

We will use **PostgreSQL Row-Level Security (RLS)** with session variables (`app.current_tenant`) to enforce tenant isolation at the database layer.

### Implementation Strategy

1. **RLS Policies:** Apply `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` to all tenant-scoped tables (`stored_events`, `snapshots`, projection tables)

2. **Tenant Isolation Policy:** Create a permissive RLS policy on each table:

   ```sql
   CREATE POLICY tenant_isolation_policy ON {table}
   FOR ALL
   USING (tenant_id = current_setting('app.current_tenant', true));
   ```

3. **Session Variable Propagation:** Use SQLAlchemy `after_begin` session event handler to automatically execute:

   ```python
   connection.execute(
       text("SELECT set_config('app.current_tenant', :tenant, true)"),
       {"tenant": tenant_id}
   )
   ```

4. **Database Trigger for Auto-Population:** Use PostgreSQL `BEFORE INSERT` triggers on event store tables to populate `tenant_id` from session variable:

   ```sql
   CREATE TRIGGER trg_stored_events_set_tenant_id
       BEFORE INSERT ON stored_events
       FOR EACH ROW
       EXECUTE FUNCTION set_tenant_id_from_context();
   ```

5. **Transaction-Scoped Safety:** Use `set_config(..., true)` (equivalent to `SET LOCAL`) to ensure context is cleared at transaction boundaries (connection pool safety)

---

## Alternatives Considered

### Alternative 1: Application-Layer Filtering Only

**Approach:** Add `WHERE tenant_id = :tenant` clauses to all queries in application code.

**Pros:**

- No database schema changes
- Simple to understand
- No performance overhead from RLS policy evaluation

**Cons:**

- No defense against SQL injection bypassing filters
- Easy to miss filters in new queries (human error)
- Direct database access (migrations, admin SQL) can leak data
- No centralized enforcement point
- Difficult to audit (requires code review of every query)

**Verdict:** Rejected. Application-layer filtering provides no security boundary.

---

### Alternative 2: Custom Eventsourcing Recorder

**Approach:** Subclass `PostgresApplicationRecorder` to inject `tenant_id` during event insertion.

**Pros:**

- Keeps tenant logic in Python (no database triggers)
- Explicit control over tenant_id population

**Cons:**

- Tight coupling with eventsourcing library internals
- Fragile (breaks on library upgrades)
- Does not enforce isolation on reads (only inserts)
- Still requires RLS for projections
- Adds complexity to event store setup

**Verdict:** Rejected. Coupling with library internals is too fragile.

---

### Alternative 3: Separate Database per Tenant

**Approach:** Create a separate PostgreSQL database for each tenant (Postgres schemas or separate DB instances).

**Pros:**

- Perfect isolation (physical separation)
- No RLS complexity
- Simpler query patterns (no tenant_id filters)

**Cons:**

- Massive operational complexity (migrations, backups, monitoring per tenant)
- Connection pool explosion (N tenants × M connections)
- Cross-tenant analytics queries become impossible
- High infrastructure cost (memory/CPU overhead per database)
- Does not scale beyond ~100 tenants

**Verdict:** Rejected. Operational complexity is prohibitive for a SaaS product targeting hundreds/thousands of tenants.

---

### Alternative 4: Middleware-Based Connection Routing

**Approach:** Use a different database connection pool per tenant, routed at middleware layer.

**Pros:**

- Strong isolation via separate connection pools
- No RLS policy evaluation overhead

**Cons:**

- Connection pool proliferation (100 tenants × 20 connections = 2000 connections)
- Complex connection management
- Still requires single database with tenant_id columns
- No benefit over RLS for same-database multi-tenancy

**Verdict:** Rejected. Does not solve core isolation problem, adds connection management complexity.

---

## Decision Rationale

### Why RLS Over Alternatives?

1. **Defense in Depth:** RLS provides database-layer enforcement independent of application code. Even if application filters fail, RLS blocks cross-tenant access.

2. **Eventsourcing Compatibility:** RLS is transparent to the eventsourcing library. No custom recorder needed. Database triggers handle `tenant_id` population.

3. **Centralized Enforcement:** All tenant isolation logic is in PostgreSQL policies (one place to audit, test, and verify).

4. **Connection Pool Safety:** `SET LOCAL` (transaction-scoped variables) prevents context leakage across pooled connections.

5. **Proven Pattern:** RLS is a mature PostgreSQL feature (since 9.5, 2016) with well-understood performance characteristics.

### Why Database Trigger for tenant_id Population?

**Considered:** Setting `tenant_id` in application code before saving events.

**Chosen:** Database trigger reads `current_setting('app.current_tenant')` and assigns to `NEW.tenant_id`.

**Rationale:**

- **Zero coupling:** Eventsourcing library remains unaware of tenants
- **Automatic:** Cannot be forgotten by developers
- **Consistent:** Works for all INSERT paths (library, admin SQL, migrations)
- **Fail-safe:** If no tenant context set, `NOT NULL` constraint fails insert (desired behavior)

---

## Trade-Offs

### Performance Impact

**Cost:** RLS adds per-row policy evaluation overhead.

**Measurement (from research):**

- Simple column comparison policies: 10-20% overhead
- Subquery-based policies: 50-100% overhead

**Mitigation:**

- Use simple `tenant_id = current_setting()` comparison (no subqueries)
- Create composite indexes with `tenant_id` as leading column
- Measured overhead acceptable for security guarantees

**Benchmark Plan:** Add optional performance test (TC-003-009) to measure actual overhead on {Project}'s event store workload.

### Operational Complexity

**Cost:** RLS policies must be managed via Alembic migrations. No native Alembic support requires raw SQL via `op.execute()`.

**Mitigation:**

- Reusable migration helpers (`migrations/helpers/rls.py`) centralize DDL patterns
- Standard policy template reduces copy-paste errors
- Integration tests verify RLS coverage across all tables

### Projection Writer Complexity

**Cost:** Projection handlers running as background tasks (no HTTP request) must explicitly set tenant context from event data.

**Mitigation:**

- Current projections run synchronously within HTTP request context (have tenant context)
- Future async projections: set context per event batch or use BYPASSRLS role
- Document pattern for projection developers

---

## Consequences

### Positive

1. **Security:** Database-layer isolation enforced independently of application code
2. **Auditability:** Single source of truth (PostgreSQL policies) for tenant isolation
3. **Eventsourcing Compatibility:** Zero modifications to eventsourcing library
4. **Connection Pool Safety:** Transaction-scoped variables prevent context leakage
5. **Defensive Testing:** Integration tests query `pg_policies` catalog to verify coverage

### Negative

1. **Performance Overhead:** 10-20% per-row evaluation cost on queries and inserts
2. **Migration Complexity:** RLS policies require raw SQL in Alembic migrations
3. **Projection Context:** Background projection writers must set tenant context explicitly (not yet implemented)
4. **Debugging:** RLS silently filters rows; missing context returns zero results (not an error)

### Neutral

1. **Admin Access:** Requires BYPASSRLS role or superuser for cross-tenant queries (intentional)
2. **Index Requirement:** All RLS tables need composite indexes with `tenant_id` as leading column (good practice anyway)
3. **Schema Change:** Adds `tenant_id VARCHAR(255)` column to event store tables (denormalization)

---

## Validation

### Feature Completion Criteria (from F-101-002)

- [x] RLS policies applied to all tenant-scoped tables
- [x] `FORCE ROW LEVEL SECURITY` enabled (table owners subject to policies)
- [x] Session event handler sets `app.current_tenant` on every transaction
- [x] Database trigger populates `tenant_id` from session variable
- [x] Integration tests validate cross-tenant isolation
- [x] Connection pool safety verified (SET LOCAL cleared after transaction)

### Success Metrics

**Isolation Tests:** 60+ integration tests across 5 tables confirm:

- Tenant A cannot read Tenant B's data
- Tenant A cannot write data with Tenant B's tenant_id
- Missing tenant context returns zero rows (default-deny)
- Context switches correctly update data visibility

**Coverage Tests:** Meta-tests verify:

- All 5 tenant-scoped tables have `tenant_isolation_policy`
- All policies use `PERMISSIVE` mode
- All policies reference `current_setting('app.current_tenant')`
- All tables have `FORCE ROW LEVEL SECURITY` enabled

---

## Implementation

**Feature:** F-101-002 Database Isolation
**Stories:**

- S-101-002-001: RLS schema migration (tenant_id columns, policies, triggers)
- S-101-002-002: SQLAlchemy session event handler
- S-101-002-003: FORCE RLS on event store tables
- S-101-002-004: RLS on projection tables
- S-101-002-005: Cross-tenant isolation tests

**Key Files:**

- `migrations/helpers/rls.py` — Reusable RLS helpers
- `src/{Project}/shared/infrastructure/persistence/tenant_context.py` — Session event handler
- `tests/integration/shared/test_cross_tenant_isolation.py` — Validation tests

**Documentation:**

- `ref-infra-rls-migration-helpers.md` — RLS helper pattern
- `ref-infra-tenant-context-handler.md` — Session event handler pattern

---

## Future Considerations

### Async Projection Runners

When projection handlers run as background tasks (outside HTTP request context), they must either:

1. Set `app.current_tenant` explicitly from event payload, OR
2. Connect as BYPASSRLS role (projection writer is trusted system component)

**Recommendation:** Use BYPASSRLS role for projection rebuild operations, explicit context for incremental projections.

### Performance Benchmarking

Add benchmark test (TC-003-009 from test strategy):

- Insert 10,000 events with RLS enabled
- Measure p50, p95, p99 latency
- Acceptance: p95 latency increase < 20%

### Cross-Tenant Analytics

For admin/support queries that need cross-tenant visibility:

- Create `{project}_admin` role with `BYPASSRLS` attribute
- Use separate `DATABASE_URL_ADMIN` for admin tools
- Audit all admin role usage

---

## References

### Research

- PostgreSQL RLS Documentation: <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>
- SQLAlchemy Session Events: <https://docs.sqlalchemy.org/en/20/orm/events.html>
- Feature Research: `_bklg/.../F-101-002/feature-research.md`

### Related ADRs

- PADR-109: Sync-First Event Sourcing (session handler works with sync/async)
- PADR-110: Application Lifecycle (handler registered at startup)
- PADR-104: Testing Strategy (testcontainers pattern for RLS tests)

### Implementation

- Feature: `_bklg/.../F-101-002/`
- Retrospective: `_bklg/.../F-101-002/retrospective.md`

---

**Status:** Proposed
**Next Steps:**

1. Human review of this ADR
2. Approve or request modifications
3. If approved, mark status as "Accepted"
4. Link from architecture bible cross-cutting security section

**Last Updated:** 2026-02-06
