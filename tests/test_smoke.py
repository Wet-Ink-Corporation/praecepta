"""Smoke tests to verify PEP 420 namespace package resolution.

Each test imports the leaf __init__.py of a praecepta package to confirm
the implicit namespace package layout works correctly under uv workspaces.
"""

from __future__ import annotations


def test_foundation_domain_importable() -> None:
    import praecepta.foundation.domain  # noqa: F401


def test_foundation_application_importable() -> None:
    import praecepta.foundation.application  # noqa: F401


def test_infra_fastapi_importable() -> None:
    import praecepta.infra.fastapi  # noqa: F401


def test_infra_eventsourcing_importable() -> None:
    import praecepta.infra.eventsourcing  # noqa: F401


def test_infra_auth_importable() -> None:
    import praecepta.infra.auth  # noqa: F401


def test_infra_persistence_importable() -> None:
    import praecepta.infra.persistence  # noqa: F401


def test_infra_observability_importable() -> None:
    import praecepta.infra.observability  # noqa: F401


def test_infra_taskiq_importable() -> None:
    import praecepta.infra.taskiq  # noqa: F401


def test_domain_tenancy_importable() -> None:
    import praecepta.domain.tenancy  # noqa: F401


def test_domain_identity_importable() -> None:
    import praecepta.domain.identity  # noqa: F401


def test_integration_tenancy_identity_importable() -> None:
    import praecepta.integration.tenancy_identity  # noqa: F401
