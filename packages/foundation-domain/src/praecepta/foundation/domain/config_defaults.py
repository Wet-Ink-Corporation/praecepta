"""System-wide default configuration values.

These defaults apply when a tenant has no explicit configuration
for a given key. Applications should populate ``SYSTEM_DEFAULTS``
at startup with their domain-specific configuration keys and values.

Example:
    Populating defaults in an application::

        from praecepta.foundation.domain.config_defaults import SYSTEM_DEFAULTS
        from praecepta.foundation.domain.config_value_objects import (
            BooleanConfigValue,
            IntegerConfigValue,
        )

        SYSTEM_DEFAULTS.update({
            "feature.dark_mode": BooleanConfigValue(value=False),
            "limits.max_items": IntegerConfigValue(value=1000),
        })
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from praecepta.foundation.domain.config_value_objects import ConfigValue

SYSTEM_DEFAULTS: dict[str, ConfigValue] = {}
"""System-wide default configuration values.

Empty by default. Applications should populate this mapping at startup
with their domain-specific defaults keyed by ConfigKey string values.
"""
