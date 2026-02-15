# Multi-Tenancy Domain

Tenant isolation, row-level security, and context propagation across all bounded contexts.

## Mental Model

Every operation is scoped to a tenant. PostgreSQL RLS (PADR-115) enforces isolation at the database level. Request context extracts tenant_id from JWT, sets it on the database session via `SET app.current_tenant`, and RLS policies filter all queries automatically.

## Invariants

- **All queries include tenant_id** (constitutional Article V)
- RLS policies on every table with tenant data
- Tenant context set before any database operation
- No cross-tenant data access possible (even via bugs)

## Key Patterns

- **Context propagation:** JWT → middleware → `request.state.tenant_id` → DB session variable
- **RLS policies:** `CREATE POLICY ... USING (tenant_id = current_setting('app.current_tenant'))`
- **Migration helpers:** RLS helper functions for schema evolution
- **Testing:** Each test gets isolated tenant_id

## Integration Points

- **→ All contexts:** Provides tenant isolation guarantee
- **← Security:** JWT provides tenant_id claim

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `_kb/decisions/patterns/PADR-115-postgresql-rls-tenant-isolation.md` | RLS implementation details |
| `references/con-request-context.md` | Context propagation |
| `references/ref-infra-tenant-context-handler.md` | Tenant handler code |
| `references/ref-infra-rls-migration-helpers.md` | RLS migrations |
