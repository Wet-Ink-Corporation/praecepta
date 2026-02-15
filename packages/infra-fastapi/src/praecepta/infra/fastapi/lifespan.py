"""Lifespan composition for the praecepta app factory.

Composes multiple :class:`~praecepta.foundation.application.LifespanContribution`
hooks into a single FastAPI-compatible lifespan context manager.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from praecepta.foundation.application import LifespanContribution

logger = logging.getLogger(__name__)


def compose_lifespan(
    hooks: list[LifespanContribution],
) -> object:
    """Create a composite lifespan from ordered :class:`LifespanContribution` hooks.

    Hooks are sorted by priority (ascending). Lower priority hooks start first
    and shut down last (stack semantics via :class:`AsyncExitStack`).

    Args:
        hooks: List of LifespanContribution instances.

    Returns:
        An async context manager factory suitable for FastAPI's ``lifespan`` parameter.
    """
    sorted_hooks = sorted(hooks, key=lambda h: h.priority)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for hook_contrib in sorted_hooks:
                logger.info(
                    "Entering lifespan hook (priority=%d): %r",
                    hook_contrib.priority,
                    hook_contrib.hook,
                )
                ctx = hook_contrib.hook(app)
                await stack.enter_async_context(ctx)
            yield

    return lifespan
