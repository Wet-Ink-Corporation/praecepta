"""Unit tests for Tenant aggregate lifecycle state machine.

Note: The eventsourcing library's @event decorator on __init__ does not
respect Python default parameter values. All parameters must be passed
explicitly. We pass config=None and metadata=None for tests that don't
need custom config.
"""

from __future__ import annotations

import pytest

from praecepta.domain.tenancy.tenant import Tenant
from praecepta.foundation.domain.aggregates import BaseAggregate
from praecepta.foundation.domain.config_value_objects import BooleanConfigValue
from praecepta.foundation.domain.exceptions import InvalidStateTransitionError
from praecepta.foundation.domain.tenant_value_objects import TenantStatus


def _new_tenant(
    *,
    slug: str = "acme-corp",
    name: str = "ACME",
    config: dict | None = None,  # type: ignore[type-arg]
    metadata: dict | None = None,  # type: ignore[type-arg]
) -> Tenant:
    """Helper to create a Tenant with sensible defaults."""
    return Tenant(tenant_id=slug, name=name, slug=slug, config=config, metadata=metadata)


@pytest.mark.unit
class TestTenantCreation:
    """Aggregate creation and initial state."""

    def test_creates_with_provisioning_status(self) -> None:
        tenant = _new_tenant()
        assert tenant.status == TenantStatus.PROVISIONING.value

    def test_extends_base_aggregate(self) -> None:
        assert issubclass(Tenant, BaseAggregate)

    def test_sets_tenant_id_to_slug(self) -> None:
        tenant = _new_tenant()
        assert tenant.tenant_id == "acme-corp"

    def test_stores_name_and_config(self) -> None:
        tenant = _new_tenant(name="ACME Corporation", config={"max_blocks": 1000})
        assert tenant.name == "ACME Corporation"
        assert tenant.config == {"max_blocks": 1000}

    def test_default_config_empty_dict(self) -> None:
        tenant = _new_tenant()
        assert tenant.config == {}

    def test_default_metadata_empty_dict(self) -> None:
        tenant = _new_tenant()
        assert tenant.metadata == {}

    def test_stores_initial_metadata(self) -> None:
        tenant = _new_tenant(metadata={"company": "ACME Inc.", "locale": "en-US"})
        assert tenant.metadata == {"company": "ACME Inc.", "locale": "en-US"}

    def test_suspension_reason_initially_none(self) -> None:
        tenant = _new_tenant()
        assert tenant.suspension_reason is None

    def test_suspension_category_initially_none(self) -> None:
        tenant = _new_tenant()
        assert tenant.suspension_category is None

    def test_decommission_reason_initially_none(self) -> None:
        tenant = _new_tenant()
        assert tenant.decommission_reason is None

    def test_rejects_invalid_slug(self) -> None:
        with pytest.raises(ValueError, match="Invalid tenant slug"):
            Tenant(tenant_id="INVALID", name="ACME", slug="INVALID", config=None, metadata=None)

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValueError, match="Tenant name cannot be empty"):
            Tenant(tenant_id="acme-corp", name="", slug="acme-corp", config=None, metadata=None)

    def test_rejects_mismatched_tenant_id_and_slug(self) -> None:
        with pytest.raises(ValueError, match="tenant_id must match slug"):
            Tenant(
                tenant_id="different-id",
                name="ACME",
                slug="acme-corp",
                config=None,
                metadata=None,
            )

    def test_records_provisioned_event(self) -> None:
        tenant = _new_tenant()
        events = tenant.collect_events()
        assert len(events) >= 1
        assert events[0].__class__.__name__ == "Provisioned"

    def test_has_uuid_id(self) -> None:
        tenant = _new_tenant()
        assert tenant.id is not None

    def test_version_starts_at_one(self) -> None:
        tenant = _new_tenant()
        assert tenant.version == 1


@pytest.mark.unit
class TestTenantActivation:
    """PROVISIONING -> ACTIVE transition."""

    def test_provisioning_to_active(self) -> None:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="admin")
        assert tenant.status == TenantStatus.ACTIVE.value

    def test_idempotent_when_already_active(self) -> None:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="admin")
        _ = tenant.collect_events()
        tenant.request_activate(initiated_by="admin")  # no-op
        assert tenant.status == TenantStatus.ACTIVE.value
        assert len(tenant.collect_events()) == 0

    def test_rejects_from_suspended(self) -> None:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="admin")
        tenant.request_suspend(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError, match="Cannot activate"):
            tenant.request_activate(initiated_by="admin")

    def test_rejects_from_decommissioned(self) -> None:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="admin")
        tenant.request_decommission(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError, match="Cannot activate"):
            tenant.request_activate(initiated_by="admin")

    def test_records_activated_event(self) -> None:
        tenant = _new_tenant()
        _ = tenant.collect_events()
        tenant.request_activate(initiated_by="admin")
        events = tenant.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Activated"

    def test_activated_event_carries_audit_metadata(self) -> None:
        tenant = _new_tenant()
        _ = tenant.collect_events()
        tenant.request_activate(initiated_by="admin-user", correlation_id="req-123")
        events = tenant.collect_events()
        ev = events[0]
        assert ev.initiated_by == "admin-user"
        assert ev.correlation_id == "req-123"

    def test_increments_version(self) -> None:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="admin")
        assert tenant.version == 2


@pytest.mark.unit
class TestTenantSuspension:
    """ACTIVE -> SUSPENDED transition."""

    def _make_active_tenant(self) -> Tenant:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        return tenant

    def test_active_to_suspended(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin")
        assert tenant.status == TenantStatus.SUSPENDED.value

    def test_stores_suspension_reason(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin", reason="payment overdue")
        assert tenant.suspension_reason == "payment overdue"

    def test_stores_suspension_category(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(
            initiated_by="billing-system",
            reason="payment overdue",
            category="billing_hold",
        )
        assert tenant.suspension_category == "billing_hold"

    def test_none_reason_stored_as_none(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin")
        assert tenant.suspension_reason is None

    def test_none_category_stored_as_none(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin")
        assert tenant.suspension_category is None

    def test_idempotent_when_already_suspended(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin")
        tenant.request_suspend(initiated_by="admin")  # no-op
        assert tenant.status == TenantStatus.SUSPENDED.value

    def test_rejects_from_provisioning(self) -> None:
        tenant = _new_tenant()
        with pytest.raises(InvalidStateTransitionError, match="Cannot suspend"):
            tenant.request_suspend(initiated_by="admin")

    def test_rejects_from_decommissioned(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_decommission(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError, match="Cannot suspend"):
            tenant.request_suspend(initiated_by="admin")

    def test_records_suspended_event(self) -> None:
        tenant = self._make_active_tenant()
        _ = tenant.collect_events()
        tenant.request_suspend(initiated_by="admin", reason="test")
        events = tenant.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Suspended"

    def test_suspended_event_carries_audit_metadata(self) -> None:
        tenant = self._make_active_tenant()
        _ = tenant.collect_events()
        tenant.request_suspend(
            initiated_by="admin-user",
            reason="billing",
            category="billing_hold",
            correlation_id="req-456",
        )
        events = tenant.collect_events()
        ev = events[0]
        assert ev.initiated_by == "admin-user"
        assert ev.correlation_id == "req-456"
        assert ev.category == "billing_hold"


@pytest.mark.unit
class TestTenantReactivation:
    """SUSPENDED -> ACTIVE transition."""

    def _make_suspended_tenant(self) -> Tenant:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        tenant.request_suspend(
            initiated_by="admin",
            reason="maintenance",
            category="admin_action",
        )
        return tenant

    def test_suspended_to_active(self) -> None:
        tenant = self._make_suspended_tenant()
        tenant.request_reactivate(initiated_by="admin")
        assert tenant.status == TenantStatus.ACTIVE.value

    def test_clears_suspension_reason(self) -> None:
        tenant = self._make_suspended_tenant()
        assert tenant.suspension_reason == "maintenance"
        tenant.request_reactivate(initiated_by="admin")
        assert tenant.suspension_reason is None

    def test_clears_suspension_category(self) -> None:
        tenant = self._make_suspended_tenant()
        assert tenant.suspension_category == "admin_action"
        tenant.request_reactivate(initiated_by="admin")
        assert tenant.suspension_category is None

    def test_idempotent_when_already_active(self) -> None:
        tenant = self._make_suspended_tenant()
        tenant.request_reactivate(initiated_by="admin")
        tenant.request_reactivate(initiated_by="admin")  # no-op
        assert tenant.status == TenantStatus.ACTIVE.value

    def test_rejects_from_provisioning(self) -> None:
        tenant = _new_tenant()
        with pytest.raises(InvalidStateTransitionError, match="Cannot reactivate"):
            tenant.request_reactivate(initiated_by="admin")

    def test_rejects_from_decommissioned(self) -> None:
        tenant = self._make_suspended_tenant()
        tenant.request_decommission(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError, match="Cannot reactivate"):
            tenant.request_reactivate(initiated_by="admin")

    def test_records_reactivated_event(self) -> None:
        tenant = self._make_suspended_tenant()
        _ = tenant.collect_events()
        tenant.request_reactivate(initiated_by="admin")
        events = tenant.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Reactivated"

    def test_reactivated_event_carries_audit_metadata(self) -> None:
        tenant = self._make_suspended_tenant()
        _ = tenant.collect_events()
        tenant.request_reactivate(initiated_by="admin-user", correlation_id="req-789")
        events = tenant.collect_events()
        ev = events[0]
        assert ev.initiated_by == "admin-user"
        assert ev.correlation_id == "req-789"


@pytest.mark.unit
class TestTenantDecommission:
    """ACTIVE|SUSPENDED -> DECOMMISSIONED (terminal)."""

    def _make_active_tenant(self) -> Tenant:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        return tenant

    def test_active_to_decommissioned(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_decommission(initiated_by="admin")
        assert tenant.status == TenantStatus.DECOMMISSIONED.value

    def test_suspended_to_decommissioned(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin")
        tenant.request_decommission(initiated_by="admin")
        assert tenant.status == TenantStatus.DECOMMISSIONED.value

    def test_stores_decommission_reason(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_decommission(initiated_by="admin", reason="customer churn")
        assert tenant.decommission_reason == "customer churn"

    def test_idempotent_when_already_decommissioned(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_decommission(initiated_by="admin")
        tenant.request_decommission(initiated_by="admin")  # no-op
        assert tenant.status == TenantStatus.DECOMMISSIONED.value

    def test_rejects_from_provisioning(self) -> None:
        tenant = _new_tenant()
        with pytest.raises(InvalidStateTransitionError, match="Cannot decommission"):
            tenant.request_decommission(initiated_by="admin")

    def test_terminal_state_blocks_activate(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_decommission(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError):
            tenant.request_activate(initiated_by="admin")

    def test_terminal_state_blocks_suspend(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_decommission(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError):
            tenant.request_suspend(initiated_by="admin")

    def test_terminal_state_blocks_reactivate(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_decommission(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError):
            tenant.request_reactivate(initiated_by="admin")

    def test_records_decommissioned_event(self) -> None:
        tenant = self._make_active_tenant()
        _ = tenant.collect_events()
        tenant.request_decommission(initiated_by="admin", reason="test")
        events = tenant.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "Decommissioned"

    def test_decommissioned_event_carries_audit_metadata(self) -> None:
        tenant = self._make_active_tenant()
        _ = tenant.collect_events()
        tenant.request_decommission(
            initiated_by="admin-user",
            reason="end of contract",
            correlation_id="req-abc",
        )
        events = tenant.collect_events()
        ev = events[0]
        assert ev.initiated_by == "admin-user"
        assert ev.correlation_id == "req-abc"


@pytest.mark.unit
class TestTenantConfigUpdate:
    """Config update on ACTIVE tenant (generic, no ConfigKey validation)."""

    def _make_active_tenant(self) -> Tenant:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        return tenant

    def test_update_config_emits_event(self) -> None:
        tenant = self._make_active_tenant()
        _ = tenant.collect_events()
        tenant.request_update_config(
            config_key="feature.dark_mode",
            config_value={"type": "boolean", "value": True},
            updated_by="admin",
        )
        events = tenant.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "ConfigUpdated"

    def test_update_config_requires_active(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin", reason="test")
        with pytest.raises(InvalidStateTransitionError, match="ACTIVE"):
            tenant.request_update_config(
                config_key="feature.dark_mode",
                config_value={"type": "boolean", "value": True},
                updated_by="admin",
            )

    def test_update_config_rejects_provisioning(self) -> None:
        tenant = _new_tenant()
        with pytest.raises(InvalidStateTransitionError):
            tenant.request_update_config(
                config_key="feature.dark_mode",
                config_value={"type": "boolean", "value": True},
                updated_by="admin",
            )

    def test_config_stored_in_aggregate(self) -> None:
        tenant = self._make_active_tenant()
        config_value = {"type": "boolean", "value": True}
        tenant.request_update_config(
            config_key="feature.dark_mode",
            config_value=config_value,
            updated_by="admin",
        )
        assert "feature.dark_mode" in tenant.config
        assert tenant.config["feature.dark_mode"] == config_value

    def test_update_config_event_payload(self) -> None:
        tenant = self._make_active_tenant()
        _ = tenant.collect_events()
        config_value = {"type": "boolean", "value": True}
        tenant.request_update_config(
            config_key="feature.dark_mode",
            config_value=config_value,
            updated_by="admin-user",
        )
        events = tenant.collect_events()
        ev = events[0]
        assert ev.config_key == "feature.dark_mode"
        assert ev.config_value == config_value
        assert ev.updated_by == "admin-user"
        assert ev.tenant_id == "acme-corp"

    def test_accepts_any_key_string(self) -> None:
        """Generic aggregate accepts any config key — validation is consumer responsibility."""
        tenant = self._make_active_tenant()
        tenant.request_update_config(
            config_key="custom.anything",
            config_value={"type": "string", "value": "hello"},
            updated_by="admin",
        )
        assert "custom.anything" in tenant.config

    def test_update_config_overwrites(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_update_config(
            config_key="feature.dark_mode",
            config_value={"type": "boolean", "value": True},
            updated_by="admin",
        )
        tenant.request_update_config(
            config_key="feature.dark_mode",
            config_value={"type": "boolean", "value": False},
            updated_by="admin",
        )
        assert tenant.config["feature.dark_mode"]["value"] is False

    def test_update_config_increments_version(self) -> None:
        tenant = self._make_active_tenant()
        version_before = tenant.version
        tenant.request_update_config(
            config_key="feature.dark_mode",
            config_value={"type": "boolean", "value": True},
            updated_by="admin",
        )
        assert tenant.version == version_before + 1

    def test_accepts_typed_config_value(self) -> None:
        """request_update_config accepts Pydantic ConfigValue objects directly."""
        tenant = self._make_active_tenant()
        typed_value = BooleanConfigValue(value=True)
        tenant.request_update_config(
            config_key="feature.dark_mode",
            config_value=typed_value,
            updated_by="admin",
        )
        assert tenant.config["feature.dark_mode"] == {"type": "boolean", "value": True}


@pytest.mark.unit
class TestTenantMetadataUpdate:
    """Metadata update on ACTIVE tenant."""

    def _make_active_tenant(self) -> Tenant:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        return tenant

    def test_update_metadata_merges(self) -> None:
        tenant = _new_tenant(metadata={"company": "ACME"})
        tenant.request_activate(initiated_by="system")
        tenant.request_update_metadata(
            metadata={"locale": "en-US"},
            updated_by="admin",
        )
        assert tenant.metadata == {"company": "ACME", "locale": "en-US"}

    def test_update_metadata_emits_event(self) -> None:
        tenant = self._make_active_tenant()
        _ = tenant.collect_events()
        tenant.request_update_metadata(
            metadata={"company": "ACME Inc."},
            updated_by="admin",
        )
        events = tenant.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "MetadataUpdated"

    def test_update_metadata_requires_active(self) -> None:
        tenant = self._make_active_tenant()
        tenant.request_suspend(initiated_by="admin")
        with pytest.raises(InvalidStateTransitionError, match="ACTIVE"):
            tenant.request_update_metadata(
                metadata={"company": "test"},
                updated_by="admin",
            )

    def test_update_metadata_overwrites_existing_keys(self) -> None:
        tenant = _new_tenant(metadata={"company": "Old Name"})
        tenant.request_activate(initiated_by="system")
        tenant.request_update_metadata(
            metadata={"company": "New Name"},
            updated_by="admin",
        )
        assert tenant.metadata["company"] == "New Name"

    def test_update_metadata_increments_version(self) -> None:
        tenant = self._make_active_tenant()
        version_before = tenant.version
        tenant.request_update_metadata(
            metadata={"timezone": "UTC"},
            updated_by="admin",
        )
        assert tenant.version == version_before + 1


@pytest.mark.unit
class TestTenantFullLifecycle:
    """Complete lifecycle produces correct event sequence."""

    def test_full_lifecycle_event_sequence(self) -> None:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        tenant.request_suspend(initiated_by="admin", reason="maintenance")
        tenant.request_reactivate(initiated_by="admin")
        tenant.request_decommission(initiated_by="admin", reason="end of service")
        assert tenant.version == 5
        assert tenant.status == TenantStatus.DECOMMISSIONED.value


@pytest.mark.unit
class TestTenantDataDeletedEvent:
    """Tests for record_data_deleted audit method."""

    def _make_decommissioned_tenant(self) -> Tenant:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        tenant.request_decommission(initiated_by="admin", reason="customer churn")
        return tenant

    def test_records_data_deleted_event(self) -> None:
        tenant = self._make_decommissioned_tenant()
        _ = tenant.collect_events()
        tenant.record_data_deleted(category="slug_reservation", entity_count=1, deleted_by="system")
        events = tenant.collect_events()
        assert len(events) == 1
        assert events[0].__class__.__name__ == "DataDeleted"

    def test_no_state_change_on_data_deleted(self) -> None:
        tenant = self._make_decommissioned_tenant()
        tenant.record_data_deleted(category="slug_reservation", entity_count=1, deleted_by="system")
        assert tenant.status == TenantStatus.DECOMMISSIONED.value

    def test_rejects_when_not_decommissioned(self) -> None:
        tenant = _new_tenant()
        tenant.request_activate(initiated_by="system")
        with pytest.raises(InvalidStateTransitionError, match="DECOMMISSIONED"):
            tenant.record_data_deleted(
                category="slug_reservation", entity_count=1, deleted_by="system"
            )

    def test_multiple_audit_events(self) -> None:
        tenant = self._make_decommissioned_tenant()
        _ = tenant.collect_events()
        tenant.record_data_deleted(category="slug_reservation", entity_count=1, deleted_by="system")
        tenant.record_data_deleted(category="projections", entity_count=5, deleted_by="admin-user")
        events = tenant.collect_events()
        assert len(events) == 2
        assert all(e.__class__.__name__ == "DataDeleted" for e in events)

    def test_version_increments_on_audit_event(self) -> None:
        tenant = self._make_decommissioned_tenant()
        version_before = tenant.version
        tenant.record_data_deleted(category="slug_reservation", entity_count=1, deleted_by="system")
        assert tenant.version == version_before + 1
