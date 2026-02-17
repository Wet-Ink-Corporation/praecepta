# Security Context

> Authentication, authorization, and access control

---

## Purpose

The Security Context manages authentication, authorization, and access control. It implements ReBAC (Relationship-Based Access Control) via an authorization engine for complex hierarchical permissions inherited from enterprise sources.

**Key Capability:** Security trimming ensures users only see content they're authorized to access, even when that content is aggregated from multiple sources with different permission models.

---

## Domain Model

### Aggregates

#### Tenant

Organizational boundary for multi-tenancy.

```python
@dataclass
class Tenant:
    """Organizational boundary."""
    id: str                         # Slug identifier
    name: str
    settings: TenantSettings
    status: TenantStatus            # ACTIVE, SUSPENDED
    created_at: datetime
```

#### User

Authenticated identity within a tenant.

```python
@dataclass
class User:
    """Authenticated user identity."""
    id: UUID
    tenant_id: str
    email: str
    display_name: str
    external_id: str | None         # IdP subject
    groups: list[Group]
    roles: list[Role]
    status: UserStatus              # ACTIVE, DISABLED
```

### Entities

#### Group

Collection of users for permission assignment.

```python
@dataclass
class Group:
    """User collection."""
    id: UUID
    tenant_id: str
    name: str
    external_id: str | None         # IdP group
    members: list[UUID]             # User IDs
```

#### Role

Permission template that can be assigned.

```python
@dataclass
class Role:
    """Permission template."""
    id: UUID
    tenant_id: str
    name: str
    permissions: tuple[Permission, ...]
    scope: RoleScope                # GLOBAL, PROJECT, TEAM
```

### Value Objects

| Value Object | Description |
|--------------|-------------|
| `Principal` | Identity reference: `user:X`, `group:Y`, `role:Z`, `tenant:T` |
| `Permission` | Enum: VIEW, EDIT, ADMIN, SHARE, DELETE |
| `AccessDecision` | ALLOW or DENY with reason |
| `ResourceType` | Enum: DOCUMENT, CHUNK, BLOCK, ENTITY |

```python
@dataclass(frozen=True)
class Principal:
    """Identity reference for authorization."""
    type: PrincipalType             # USER, GROUP, ROLE, TENANT
    id: str

    def __str__(self) -> str:
        return f"{self.type.value}:{self.id}"

@dataclass(frozen=True)
class AccessDecision:
    """Authorization decision."""
    allowed: bool
    reason: str | None
    checked_at: datetime
```

---

## Domain Events

```python
# User Events
@dataclass(frozen=True)
class UserCreated(SecurityEvent):
    """Emitted when a user is created."""
    tenant_id: str
    email: str
    external_id: str | None

@dataclass(frozen=True)
class UserGroupsUpdated(SecurityEvent):
    """Emitted when user's groups change."""
    added_groups: tuple[UUID, ...]
    removed_groups: tuple[UUID, ...]

@dataclass(frozen=True)
class UserDisabled(SecurityEvent):
    """Emitted when a user is disabled."""
    reason: str
    disabled_by: UUID

# Access Events
@dataclass(frozen=True)
class AccessGranted(SecurityEvent):
    """Emitted when access is granted."""
    principal: str
    resource_type: str
    resource_id: UUID
    permission: str
    granted_by: UUID

@dataclass(frozen=True)
class AccessRevoked(SecurityEvent):
    """Emitted when access is revoked."""
    principal: str
    resource_type: str
    resource_id: UUID
    permission: str
    revoked_by: UUID

# Audit Events
@dataclass(frozen=True)
class AccessDenied(SecurityEvent):
    """Emitted when access is denied (audit trail)."""
    user_id: UUID
    resource_type: str
    resource_id: UUID
    permission: str
    reason: str
```

---

## ReBAC Schema

{Project} uses a ReBAC engine for relationship-based access control:

```zed
definition user {}

definition group {
    relation member: user
}

definition tenant {
    relation admin: user
    relation member: user | group#member

    permission manage = admin
    permission view = member + admin
}

definition folder {
    relation owner: user
    relation parent: folder
    relation viewer: user | group#member | tenant#member

    permission view = viewer + owner + parent->view
    permission edit = owner + parent->edit
}

definition document {
    relation owner: user
    relation parent: folder
    relation viewer: user | group#member | tenant#member

    permission view = viewer + owner + parent->view
    permission edit = owner
}

definition chunk {
    relation parent: document

    permission view = parent->view
}

definition memory_block {
    relation owner: user
    relation participant: user | group#member

    permission view = participant + owner
    permission edit = owner
    permission manage = owner
    permission add_content = participant + owner
}

definition entity {
    relation source: document

    permission view = source->view
}
```

---

## Key Operations

### Check Permission

```python
class CheckPermissionHandler:
    """Checks if a user has permission on a resource."""

    def __init__(self, authz: AuthorizationPort):
        self.authz = authz

    async def handle(self, query: CheckPermission) -> AccessDecision:
        result = await self.authz.check_permission(
            subject=f"user:{query.user_id}",
            permission=query.permission.value,
            resource=f"{query.resource_type.value}:{query.resource_id}",
        )

        if not result.allowed:
            # Emit audit event
            await self._emit_access_denied(query)

        return AccessDecision(
            allowed=result.allowed,
            reason=result.reason if not result.allowed else None,
            checked_at=datetime.utcnow(),
        )
```

### Security Trimming

Two-phase approach for performance:

```python
class SecurityTrimmingService:
    """Filters content based on user permissions."""

    async def get_allowed_principals(self, user_id: UUID) -> set[str]:
        """Get all principals a user resolves to (for pre-filtering)."""
        user = await self.user_repo.get(user_id)

        principals = {f"user:{user_id}"}
        principals.add(f"tenant:{user.tenant_id}")

        for group in user.groups:
            principals.add(f"group:{group.id}")

        return principals

    async def pre_filter(
        self,
        user_id: UUID,
        content_ids: list[UUID],
    ) -> list[UUID]:
        """Fast pre-filter using denormalized ACLs."""
        principals = await self.get_allowed_principals(user_id)

        # Filter using denormalized principals in search index
        return await self.acl_index.filter_by_principals(
            content_ids=content_ids,
            principals=principals,
        )

    async def post_filter(
        self,
        user_id: UUID,
        content_ids: list[UUID],
    ) -> list[UUID]:
        """Accurate post-filter using authorization engine."""
        allowed = []
        for content_id in content_ids:
            decision = await self.check_permission(
                user_id=user_id,
                resource_type=ResourceType.CHUNK,
                resource_id=content_id,
                permission=Permission.VIEW,
            )
            if decision.allowed:
                allowed.append(content_id)
        return allowed
```

### Sync ACLs from Source

```python
class SyncACLsHandler:
    """Syncs ACLs from external source systems."""

    async def handle(self, command: SyncSourceACLs) -> list[SecurityEvent]:
        events = []

        # Get ACLs from source system
        source_acls = await self.source_connector.get_acls(
            source_type=command.source_type,
            source_id=command.source_id,
        )

        for acl in source_acls:
            # Map external principal to internal
            internal_principal = await self._map_principal(acl.principal)

            # Grant access
            events.append(AccessGranted(
                originator_id=command.document_id,
                principal=str(internal_principal),
                resource_type="document",
                resource_id=command.document_id,
                permission=self._map_permission(acl.permission),
                granted_by=SYSTEM_USER_ID,
            ))

            # Write relationship to authorization engine
            await self.authz.write_relationship(
                subject=str(internal_principal),
                relation=self._map_relation(acl.permission),
                resource=f"document:{command.document_id}",
            )

        return events
```

---

## Integration Patterns

| Integrates With | Pattern | Direction | Purpose |
|-----------------|---------|-----------|---------|
| **Query** | Facade | Provides | Security trimming checks |
| **Memory** | Facade | Provides | Block access validation |
| **Ingestion** | Facade | Provides | Source system ACL mapping |
| **Graph** | Facade | Provides | Entity/relationship visibility |

### Facade Interface

```python
class SecurityFacade:
    """Public interface for other contexts."""

    async def check_permission(
        self,
        user_id: UUID,
        resource_type: ResourceType,
        resource_id: UUID,
        permission: Permission,
    ) -> bool:
        """Check if user has permission."""
        ...

    async def get_allowed_principals(self, user_id: UUID) -> set[str]:
        """Get all principals user resolves to."""
        ...

    async def bulk_check(
        self,
        user_id: UUID,
        checks: list[PermissionCheck],
    ) -> dict[UUID, bool]:
        """Batch permission check for performance."""
        ...

    async def get_user(self, user_id: UUID) -> UserDTO | None:
        """Get user details."""
        ...
```

---

## External Integrations

### Identity Providers

| Provider | Protocol | Sync Method |
|----------|----------|-------------|
| Azure AD | OIDC | SCIM 2.0 |
| Okta | OIDC | SCIM 2.0 |
| Google Workspace | OIDC | Directory API |

### Authorization

| Service | Purpose |
|---------|---------|
| ReBAC Engine | Relationship-based permission checks |
| OIDC Provider | JWT issuance, session management |

---

## Package Structure

```
src/{project}/security/
├── __init__.py
├── application.py
├── facade.py
│
├── _shared/
│   ├── events.py               # UserCreated, AccessGranted, etc.
│   ├── exceptions.py           # UnauthorizedError, etc.
│   └── common.py
│
├── domain/
│   ├── aggregates.py           # Tenant, User
│   ├── entities.py             # Group, Role
│   └── value_objects.py        # Principal, Permission
│
├── slices/
│   ├── authenticate/
│   ├── check_permission/
│   ├── grant_access/
│   ├── revoke_access/
│   └── sync_source_acls/
│
├── projections/
│   └── audit_log_projection.py
│
└── infrastructure/
    ├── api.py
    ├── authz_adapter.py
    ├── oidc_adapter.py
    └── scim_adapter.py
```

---

## See Also

- [Query Context](con-query-context.md) - Consumes security trimming
- [Ingestion Context](con-ingestion-context.md) - Syncs source ACLs
