"""Supported policy types for tenant default policy bindings.

PolicyType is an extensible StrEnum base class. Applications should subclass
it with their own domain-specific policy types and provide a mapping from
policy types to configuration keys.

Example:
    Extending PolicyType in an application::

        from praecepta.foundation.domain.policy_types import PolicyType

        class MyAppPolicyType(PolicyType):
            DECAY_STRATEGY = "decay_strategy"
            RETENTION_PERIOD = "retention_period"

        # Then provide a POLICY_TYPE_TO_CONFIG_KEY mapping:
        POLICY_TYPE_TO_CONFIG_KEY = {
            MyAppPolicyType.DECAY_STRATEGY: MyAppConfigKey.DEFAULT_DECAY_STRATEGY,
            MyAppPolicyType.RETENTION_PERIOD: MyAppConfigKey.DEFAULT_RETENTION_DAYS,
        }
"""

from __future__ import annotations

from enum import StrEnum


class PolicyType(StrEnum):
    """Extensible registry of supported policy types for default binding configuration.

    This is an empty base class. Applications should extend it with their own
    domain-specific policy types. Each policy type typically maps to a
    ConfigKey in the tenant configuration system.

    Values typically match URL path parameters:
    ``/config/policies/{policy_type}``

    Applications must also provide a ``POLICY_TYPE_TO_CONFIG_KEY`` mapping
    from their extended PolicyType to the corresponding ConfigKey.

    Example::

        class MyPolicyType(PolicyType):
            DECAY_STRATEGY = "decay_strategy"
            RETENTION_PERIOD = "retention_period"
    """
