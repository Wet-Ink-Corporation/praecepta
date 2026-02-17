# Security Domain

Authentication, authorization, and access control. JWT-based AuthN with ReBAC engine for fine-grained AuthZ.

## Mental Model

Two layers: **AuthN** via external OIDC provider (JWT + JWKS, PADR-116/122) and **AuthZ** via Zanzibar-style relationship-based access control (PADR-004). Request context carries tenant_id + principal, propagated through all layers. Security trimming applies at query time, not storage time (PADR-004).

## Invariants

- Every request must have a valid JWT with tenant_id claim
- ReBAC relationships define resource-level permissions
- Dev bypass available but guarded by environment flag

## Key Patterns

- **Middleware:** JWT validation → Principal extraction → Tenant context injection
- **OIDC flow:** Authorization Code + PKCE → Token exchange → Session management
- **Session:** Refresh token rotation, session listing, revocation
- **ACL model:** Tiered inheritance from source systems

## Integration Points

- **→ All contexts:** Provides tenant_id + principal via request context
- **← OIDC Provider:** External identity provider for authentication
- **← Authorization Engine:** External ReBAC engine for fine-grained permissions

## Reference Index

| Reference | Load When |
|-----------|-----------|
| `references/con-security-context.md` | Designing security features |
| `references/con-security-model.md` | Security architecture overview |
| `_kb/decisions/strategic/PADR-004-security-trimming.md` | Query-time filtering rationale |
| `_kb/decisions/patterns/PADR-115-postgresql-rls-tenant-isolation.md` | RLS implementation |
| `_kb/decisions/patterns/PADR-116-jwt-auth-jwks.md` | JWT validation patterns |
| `references/security-access-control.md` | ACL model design |

