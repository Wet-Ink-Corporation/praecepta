# Architecture Decision Records

25 PADRs governing praecepta framework architecture. Renumbered from source project ADRs.

> **Numbering convention:** Strategic decisions use 001–0xx, pattern decisions use 101–1xx.
> PADR-003 and PADR-117 were intentionally skipped during renumbering from the source project.

## Strategic Decisions

| PADR | Title | Status |
|------|-------|--------|
| PADR-001 | Event Sourcing | Accepted |
| PADR-002 | Modular Monolith | Accepted |
| PADR-004 | Security Trimming | Accepted |
| PADR-005 | Task Queue (Redis/TaskIQ) | Accepted |

## Pattern Decisions

| PADR | Title | Status |
|------|-------|--------|
| PADR-101 | Vertical Slices | Accepted |
| PADR-102 | Hexagonal Ports and Adapters | Accepted |
| PADR-103 | Error Handling | Accepted |
| PADR-104 | Testing Strategy | Accepted |
| PADR-105 | Observability | Accepted |
| PADR-106 | Configuration (Pydantic Settings) | Accepted |
| PADR-107 | API Documentation (OpenAPI) | Accepted |
| PADR-108 | Domain Service Protocols | Accepted |
| PADR-109 | Sync-First Event Sourcing | Accepted |
| PADR-110 | Application Lifecycle | Accepted |
| PADR-111 | ClassVar Aggregate Type Discrimination | Accepted |
| PADR-112 | Module-Level Registry | Accepted |
| PADR-113 | Two-Tier Validation | Accepted |
| PADR-114 | Aggregate Lifecycle State Machine | Accepted |
| PADR-115 | PostgreSQL RLS Tenant Isolation | Accepted |
| PADR-116 | JWT Auth with JWKS | Accepted |
| PADR-118 | JIT User Provisioning | Accepted |
| PADR-119 | Separate User Application | Accepted |
| PADR-120 | Multi-Auth Middleware Sequencing | Accepted |
| PADR-121 | Projection-Based Authentication | Accepted |
| PADR-122 | Entry-Point Auto-Discovery | Accepted |

## File Locations

- Strategic: `decisions/strategic/PADR-NNN-*.md`
- Pattern: `decisions/patterns/PADR-NNN-*.md`
