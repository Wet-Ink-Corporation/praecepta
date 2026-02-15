"""Entry-point-based auto-discovery utilities.

Provides helpers for loading contributions from installed packages using
Python's standard ``importlib.metadata.entry_points()`` mechanism.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscoveredContribution:
    """A single discovered entry point contribution.

    Attributes:
        name: Entry point name (e.g., ``"tenancy"``).
        group: Entry point group (e.g., ``"praecepta.routers"``).
        value: The loaded Python object.
    """

    name: str
    group: str
    value: Any


def discover(
    group: str,
    *,
    exclude_names: frozenset[str] = frozenset(),
) -> list[DiscoveredContribution]:
    """Discover and load all entry points for a given group.

    Iterates over installed packages' entry points in the specified group,
    loads each one, and returns them as :class:`DiscoveredContribution` instances.
    Entry points that fail to load are logged and skipped (fail-soft).

    Args:
        group: The entry point group name (e.g., ``"praecepta.routers"``).
        exclude_names: Set of entry point names to skip.

    Returns:
        List of successfully loaded contributions.
    """
    contributions: list[DiscoveredContribution] = []
    eps = entry_points(group=group)

    for ep in eps:
        if ep.name in exclude_names:
            logger.debug("Skipping excluded entry point %s:%s", group, ep.name)
            continue
        try:
            loaded = ep.load()
            contributions.append(DiscoveredContribution(name=ep.name, group=group, value=loaded))
            logger.debug("Loaded entry point %s:%s", group, ep.name)
        except Exception:
            logger.exception("Failed to load entry point %s:%s", group, ep.name)

    logger.info("Discovered %d contributions in group %r", len(contributions), group)
    return contributions
