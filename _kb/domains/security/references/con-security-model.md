# Security Model

> ACL architecture, authentication, and authorization patterns

---

## Overview

{Project} implements enterprise-grade security through a combination of authentication (external OIDC provider), authorization (ReBAC engine), and security trimming. This document describes the crosscutting security patterns applied across all bounded contexts.

---

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SECURITY ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    IDENTITY LAYER                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│  │  │  Azure AD   │  │    Okta     │  │   Google    │  ← External IdPs │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │   │
│  │         └────────────────┼────────────────┘                         │   │
│  │                          │ OIDC/SAML                                │   │
│  │                          ▼                                          │   │
│  │                  ┌─────────────┐                                    │   │
│  │                  │OIDC Provider│ ← Central Identity Broker          │   │
│  │                  │ (JWT Issue) │                                    │   │
│  │                  └──────┬──────┘                                    │   │
│  └─────────────────────────┼───────────────────────────────────────────┘   │
│                            │ JWT Token                                      │
│                            ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                  AUTHORIZATION LAYER                                 │   │
│  │                                                                      │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │                      ReBAC Engine                               │  │   │
│  │  │              (Relationship-Based Access Control)               │  │   │
│  │  │                                                                │  │   │
│  │  │  user:alice ──[member]─▶ group:engineering                    │  │   │
│  │  │  group:engineering ──[viewer]─▶ folder:project-x              │  │   │
│  │  │  document:doc-123 ──[parent]─▶ folder:project-x               │  │   │
│  │  │  ∴ user:alice has [view] on document:doc-123                  │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                            │                                                │
│                            ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   APPLICATION LAYER                                  │   │
│  │                                                                      │   │
│  │  Query → Pre-Filter → Retrieval → Post-Filter → Response            │   │
│  │            (ACL hash)           (ReBAC engine)                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Authentication

### JWT Token Flow

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt

bearer_scheme = HTTPBearer()

class AuthenticatedUser:
    """Authenticated user from JWT."""
    user_id: UUID
    tenant_id: str
    email: str
    groups: list[str]
    roles: list[str]

async def get_current_user(
    token: str = Depends(bearer_scheme),
    jwks: JWKS = Depends(get_jwks),
) -> AuthenticatedUser:
    """Extract and validate JWT token."""
    try:
        payload = jwt.decode(
            token.credentials,
            jwks,
            algorithms=["RS256"],
            audience="{app}-api",
            issuer="https://auth.example.com",
        )

        return AuthenticatedUser(
            user_id=UUID(payload["sub"]),
            tenant_id=payload["tenant_id"],
            email=payload["email"],
            groups=payload.get("groups", []),
            roles=payload.get("roles", []),
        )

    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )
```

### Token Structure

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "iss": "https://auth.example.com",
  "aud": "{app}-api",
  "exp": 1704067200,
  "iat": 1704063600,
  "tenant_id": "acme-corp",
  "email": "alice@acme.com",
  "groups": ["engineering", "project-x-team"],
  "roles": ["user", "project-admin"]
}
```

---

## Authorization Model

### Principals

| Principal Type | Format | Example | Description |
|----------------|--------|---------|-------------|
| `user` | `user:{uuid}` | `user:alice-123` | Individual user |
| `group` | `group:{uuid}` | `group:engineering` | Collection of users |
| `role` | `role:{name}` | `role:admin` | Permission template |
| `tenant` | `tenant:{slug}` | `tenant:acme` | Organization |

### Permissions

| Permission | Description | Typical Use |
|------------|-------------|-------------|
| `view` | Read access | Query content |
| `edit` | Modify access | Update content |
| `delete` | Remove access | Archive/delete |
| `share` | Grant access | Share with others |
| `manage` | Full control | Admin operations |

### Permission Inheritance

```
tenant:acme
    │
    ├──[admin]──▶ user:alice (tenant admin)
    │
    └──[member]──▶ group:engineering
                       │
                       └──[viewer]──▶ folder:project-x
                                          │
                                          └──[parent]──▶ document:doc-123
                                                              │
                                                              └──[parent]──▶ chunk:chunk-456

∴ All engineering group members can VIEW chunk:chunk-456
```

---

## Security Trimming

### Two-Phase Approach

Security trimming uses two phases for optimal performance:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY TRIMMING                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Query: "machine learning best practices"                                    │
│  User: alice@acme.com                                                        │
│                                                                              │
│  Phase 1: PRE-FILTER (Fast, Approximate)                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. Resolve user to principals:                                      │   │
│  │     user:alice → [user:alice, group:eng, tenant:acme]               │   │
│  │                                                                      │   │
│  │  2. Query with ACL hash filter:                                      │   │
│  │     SELECT * FROM chunks                                             │   │
│  │     WHERE embedding <-> query_vector < 0.5                          │   │
│  │       AND acl_principals && ARRAY['user:alice','group:eng',...]     │   │
│  │     LIMIT 100                                                        │   │
│  │                                                                      │   │
│  │  Result: 100 candidate chunks (fast, ~50ms)                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                          │
│                                   ▼                                          │
│  Phase 2: POST-FILTER (Accurate, Authoritative)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. For each candidate, check ReBAC engine:                           │   │
│  │     CheckPermission(user:alice, view, chunk:chunk-123)              │   │
│  │                                                                      │   │
│  │  2. ReBAC engine resolves full relationship graph:                   │   │
│  │     - Check direct permissions                                       │   │
│  │     - Check group membership                                         │   │
│  │     - Check folder/document inheritance                              │   │
│  │     - Apply deny rules                                               │   │
│  │                                                                      │   │
│  │  Result: 85 authorized chunks (accurate, ~100ms)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class SecurityTrimmingService:
    """Two-phase security trimming for search results."""

    def __init__(
        self,
        authz: AuthorizationAdapter,
        user_repo: UserRepository,
    ):
        self.authz = authz
        self.user_repo = user_repo

    async def resolve_principals(self, user_id: UUID) -> set[str]:
        """Resolve user to all applicable principals."""
        user = await self.user_repo.get(user_id)

        principals = {f"user:{user_id}"}
        principals.add(f"tenant:{user.tenant_id}")

        for group in user.groups:
            principals.add(f"group:{group.id}")

        for role in user.roles:
            principals.add(f"role:{role.name}")

        return principals

    async def pre_filter(
        self,
        user_id: UUID,
        candidate_ids: list[UUID],
    ) -> list[UUID]:
        """Fast pre-filter using denormalized ACL hashes."""
        principals = await self.resolve_principals(user_id)
        principal_hash = self._compute_hash(principals)

        # Filter using index
        return await self.vector_store.filter_by_acl_hash(
            candidate_ids=candidate_ids,
            acl_hash=principal_hash,
        )

    async def post_filter(
        self,
        user_id: UUID,
        candidate_ids: list[UUID],
    ) -> list[UUID]:
        """Accurate post-filter using ReBAC engine."""
        # Batch check for performance
        checks = [
            CheckPermissionRequest(
                subject=f"user:{user_id}",
                permission="view",
                resource=f"chunk:{chunk_id}",
            )
            for chunk_id in candidate_ids
        ]

        results = await self.authz.bulk_check(checks)

        return [
            chunk_id
            for chunk_id, allowed in zip(candidate_ids, results)
            if allowed
        ]
```

### ACL Denormalization

Store principal arrays for fast pre-filtering:

```python
class ACLDenormalizer:
    """Denormalize ACLs for fast pre-filtering."""

    async def denormalize_document(
        self,
        document_id: UUID,
    ) -> list[str]:
        """Get all principals with view access to document."""
        # Query authorization engine for all viewers
        principals = await self.authz.lookup_subjects(
            resource=f"document:{document_id}",
            permission="view",
            subject_type="user",
        )

        # Also get groups
        groups = await self.authz.lookup_subjects(
            resource=f"document:{document_id}",
            permission="view",
            subject_type="group",
        )

        return principals + groups

    async def update_chunk_acls(
        self,
        chunk_id: UUID,
        document_id: UUID,
    ) -> None:
        """Update denormalized ACLs on chunk."""
        principals = await self.denormalize_document(document_id)

        await self.vector_store.update_metadata(
            chunk_id=chunk_id,
            metadata={"acl_principals": principals},
        )
```

---

## Multi-Tenancy

### Tenant Isolation

```python
class TenantMiddleware:
    """Ensure tenant isolation in all operations."""

    async def __call__(self, request: Request, call_next):
        user: AuthenticatedUser = request.state.user
        tenant_id = user.tenant_id

        # Set tenant context for all database operations
        set_tenant_context(tenant_id)

        # All queries will be filtered by tenant
        response = await call_next(request)

        return response

class TenantAwareRepository(Generic[T]):
    """Repository with automatic tenant filtering."""

    async def get(self, id: UUID) -> T | None:
        tenant_id = get_tenant_context()
        return await self._db.fetchone(
            "SELECT * FROM {} WHERE id = $1 AND tenant_id = $2",
            self._table,
            id,
            tenant_id,
        )

    async def list(self, **filters) -> list[T]:
        tenant_id = get_tenant_context()
        return await self._db.fetch(
            "SELECT * FROM {} WHERE tenant_id = $1",
            self._table,
            tenant_id,
        )
```

### Cross-Tenant Prevention

```python
class TenantBoundaryEnforcer:
    """Prevent cross-tenant data access."""

    def validate_access(
        self,
        user: AuthenticatedUser,
        resource_tenant: str,
    ) -> None:
        """Ensure user can only access their tenant's data."""
        if user.tenant_id != resource_tenant:
            raise CrossTenantAccessError(
                f"User {user.user_id} from tenant {user.tenant_id} "
                f"cannot access resource from tenant {resource_tenant}"
            )
```

---

## ACL Synchronization

### Source System Integration

```python
class ACLSyncService:
    """Sync ACLs from external source systems."""

    async def sync_confluence_acls(
        self,
        space_key: str,
        page_id: str,
    ) -> None:
        """Sync ACLs from Confluence."""
        # Get Confluence permissions
        confluence_perms = await self.confluence.get_permissions(
            space_key=space_key,
            page_id=page_id,
        )

        # Map to authorization engine relationships
        for perm in confluence_perms:
            subject = await self._map_confluence_principal(perm.principal)
            relation = self._map_confluence_operation(perm.operation)

            await self.authz.write_relationship(
                subject=subject,
                relation=relation,
                resource=f"document:{page_id}",
            )

    async def sync_sharepoint_acls(
        self,
        site_id: str,
        item_id: str,
    ) -> None:
        """Sync ACLs from SharePoint."""
        # Get SharePoint permissions
        sp_perms = await self.sharepoint.get_permissions(
            site_id=site_id,
            item_id=item_id,
        )

        # Map to authorization engine relationships
        for perm in sp_perms:
            subject = await self._map_sharepoint_principal(perm)
            relation = self._map_sharepoint_role(perm.role)

            await self.authz.write_relationship(
                subject=subject,
                relation=relation,
                resource=f"document:{item_id}",
            )
```

### ACL Update Propagation

```python
class ACLPropagationHandler:
    """Handle ACL changes and propagate to search indexes."""

    async def handle(self, event: AccessGranted | AccessRevoked) -> None:
        """Propagate ACL change to all affected content."""
        match event:
            case AccessGranted():
                # Find all chunks for this document
                chunks = await self.chunk_repo.find_by_document(
                    event.resource_id
                )

                # Update denormalized ACLs
                for chunk in chunks:
                    principals = await self.acl_service.denormalize_document(
                        event.resource_id
                    )
                    await self.vector_store.update_metadata(
                        chunk_id=chunk.id,
                        metadata={"acl_principals": principals},
                    )

            case AccessRevoked():
                # Same process for revocation
                chunks = await self.chunk_repo.find_by_document(
                    event.resource_id
                )

                for chunk in chunks:
                    principals = await self.acl_service.denormalize_document(
                        event.resource_id
                    )
                    await self.vector_store.update_metadata(
                        chunk_id=chunk.id,
                        metadata={"acl_principals": principals},
                    )
```

---

## Audit Logging

### Audit Events

```python
@dataclass(frozen=True)
class AuditEvent:
    """Security audit event."""
    id: UUID
    timestamp: datetime
    tenant_id: str
    user_id: UUID
    action: AuditAction
    resource_type: str
    resource_id: UUID
    outcome: AuditOutcome  # SUCCESS, DENIED, ERROR
    details: dict
    ip_address: str | None
    user_agent: str | None

class AuditLogger:
    """Log all security-relevant events."""

    async def log_access(
        self,
        user: AuthenticatedUser,
        resource_type: str,
        resource_id: UUID,
        action: str,
        outcome: str,
        **details,
    ) -> None:
        event = AuditEvent(
            id=uuid4(),
            timestamp=datetime.utcnow(),
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            action=AuditAction(action),
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=AuditOutcome(outcome),
            details=details,
            ip_address=get_client_ip(),
            user_agent=get_user_agent(),
        )

        await self._store.append(event)
```

### Audit Queries

```sql
-- Failed access attempts in last 24h
SELECT user_id, COUNT(*) as failures
FROM audit_log
WHERE outcome = 'DENIED'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY user_id
HAVING COUNT(*) > 10;

-- Resource access history
SELECT *
FROM audit_log
WHERE resource_type = 'document'
  AND resource_id = $1
ORDER BY timestamp DESC
LIMIT 100;
```

---

## Security Decorators

### Endpoint Protection

```python
from functools import wraps

def require_permission(
    resource_type: str,
    permission: Permission,
    resource_id_param: str = "id",
):
    """Decorator to enforce permission on endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(
            *args,
            user: AuthenticatedUser = Depends(get_current_user),
            security: SecurityFacade = Depends(get_security),
            **kwargs,
        ):
            resource_id = kwargs.get(resource_id_param)

            allowed = await security.check_permission(
                user_id=user.user_id,
                resource_type=ResourceType(resource_type),
                resource_id=resource_id,
                permission=permission,
            )

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No {permission.value} permission on {resource_type}",
                )

            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

# Usage
@router.get("/blocks/{block_id}")
@require_permission("memory_block", Permission.VIEW)
async def get_block(block_id: UUID, user: AuthenticatedUser):
    ...

@router.delete("/blocks/{block_id}")
@require_permission("memory_block", Permission.DELETE)
async def delete_block(block_id: UUID, user: AuthenticatedUser):
    ...
```

---

## See Also

- [Security Context](../05-building-blocks/bounded-contexts/con-security-context.md)
- [Query Flow](../06-runtime/proc-query-flow.md) - Security trimming in action
- [External Systems](../03-context/ref-external-systems.md) - Identity providers
- [PADR-004: Security Trimming](../09-decisions/strategic/PADR-004-security-trimming.md)
