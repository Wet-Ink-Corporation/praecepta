"""Cascade deletion service for decommissioned tenants.

Removes shared-context tenant data with audit logging. Preserves event
store events (soft-delete principle). Physical deletion of events is
deferred to a future background process.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class CascadeDeletionResult:
    """Result of cascade deletion operation.

    Attributes:
        projections_deleted: Count of projection rows removed.
        slug_released: Whether the slug reservation was marked for release.
        categories_processed: List of data categories that were processed.
    """

    projections_deleted: int = 0
    slug_released: bool = False
    categories_processed: list[str] = field(default_factory=list)


class CascadeDeletionService:
    """Synchronous cascade deletion for shared-context tenant data.

    Executes within the handler's synchronous call chain.

    Deletion targets (shared context only):
    1. Projection tables scoped by tenant_id (physical delete -- not event-sourced)
    2. Event store events are NOT deleted (immutability principle)

    Not handled here (out of scope):
    - Slug registry release (handled by handler after cascade)
    - Cross-context data (deferred to integration packages)
    """

    def delete_tenant_data(
        self,
        tenant_slug: str,
        aggregate_id: UUID,
    ) -> CascadeDeletionResult:
        """Delete all shared-context data for a decommissioned tenant.

        Currently a lightweight operation. As projections are added,
        this method will be extended to delete rows from those tables.

        Args:
            tenant_slug: Tenant slug identifier (used for projection queries).
            aggregate_id: Tenant aggregate UUID (used for event store queries).

        Returns:
            CascadeDeletionResult with counts of deleted items.
        """
        result = CascadeDeletionResult()

        logger.info(
            "cascade_deletion_started",
            extra={
                "tenant_slug": tenant_slug,
                "aggregate_id": str(aggregate_id),
            },
        )

        # Phase 1: Delete tenant-scoped projection rows
        # Extension point: add projection cleanup here as projections
        # are introduced.

        # Phase 2: Mark slug for release
        # The actual slug registry deletion is performed by the handler
        # after audit events are recorded. We just flag it here.
        result.slug_released = True
        result.categories_processed.append("slug_reservation")

        logger.info(
            "cascade_deletion_completed",
            extra={
                "tenant_slug": tenant_slug,
                "aggregate_id": str(aggregate_id),
                "projections_deleted": result.projections_deleted,
                "categories_processed": result.categories_processed,
            },
        )

        return result
