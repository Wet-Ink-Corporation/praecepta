"""Shared fixtures for domain-identity tests."""

from __future__ import annotations

import pytest

from praecepta.domain.identity.agent import Agent
from praecepta.domain.identity.user import User


@pytest.fixture()
def user() -> User:
    """Create a User with default OIDC claims."""
    return User(
        oidc_sub="test-oidc-sub-123",
        tenant_id="acme-corp",
        email="user@example.com",
        name="Test User",
    )


@pytest.fixture()
def agent() -> Agent:
    """Create an Agent in ACTIVE state."""
    return Agent(
        agent_type_id="test-bot",
        tenant_id="acme-corp",
        display_name="Test Bot",
    )
