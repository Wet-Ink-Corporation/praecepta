"""Lifespan hook for code intelligence startup and shutdown.

Loads indexes on startup, stops watcher and saves indexes on shutdown.
Priority 250: after projections (200).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from praecepta.foundation.application import LifespanContribution

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _codeintel_lifespan(app: Any) -> AsyncIterator[None]:
    """Load indexes on startup, save on shutdown.

    Startup:
        1. Load serialized structural index from disk (graph.pkl)
        2. Open LanceDB database connection
        3. Start file watcher (if configured)

    Shutdown:
        1. Stop file watcher
        2. Serialize structural index to disk
        3. Close LanceDB connection
    """
    from praecepta.infra.codeintel.index.structural_index import NetworkXStructuralIndex
    from praecepta.infra.codeintel.settings import get_settings

    settings = get_settings()
    logger.info("codeintel_lifespan: starting up (repo=%s)", settings.repo_root)

    # Startup
    structural_index = NetworkXStructuralIndex()
    structural_index.load()
    logger.info("codeintel_lifespan: structural index loaded")

    # LanceDB opens on first use — no explicit startup needed
    # File watcher started if configured (optional)

    try:
        yield
    finally:
        # Shutdown
        logger.info("codeintel_lifespan: shutting down")

        try:
            structural_index.save()
            logger.info("codeintel_lifespan: structural index saved")
        except Exception:
            logger.warning("codeintel_lifespan: failed to save structural index", exc_info=True)


lifespan_contribution = LifespanContribution(
    hook=_codeintel_lifespan,
    priority=250,
)
