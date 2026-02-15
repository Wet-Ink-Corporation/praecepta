"""Typed configuration value objects for tenant configuration.

Uses Pydantic discriminated unions for type-safe configuration values.
ConfigKey is an extensible StrEnum base class -- applications should subclass
it with their own domain-specific keys.

Example:
    Extending ConfigKey in an application::

        from praecepta.foundation.domain.config_value_objects import ConfigKey

        class MyAppConfigKey(ConfigKey):
            FEATURE_DARK_MODE = "feature.dark_mode"
            MAX_ITEMS = "limits.max_items"

        # Then provide a CONFIG_KEY_TYPES mapping in your application:
        CONFIG_KEY_TYPES: dict[MyAppConfigKey, set[str]] = {
            MyAppConfigKey.FEATURE_DARK_MODE: {"boolean", "percentage"},
            MyAppConfigKey.MAX_ITEMS: {"integer"},
        }
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ConfigKey(StrEnum):
    """Extensible registry of tenant configuration keys.

    This is an empty base class. Applications should extend it with their own
    configuration keys organized by namespace:

    - ``feature.*`` : Feature flags (boolean or percentage)
    - ``limits.*``  : Resource capacity limits (integer)
    - ``policy.*``  : Policy binding defaults (string/enum)

    Applications must also provide a ``CONFIG_KEY_TYPES`` mapping from their
    extended ConfigKey to the set of allowed ConfigValue type discriminators.

    Example::

        class MyConfigKey(ConfigKey):
            FEATURE_GRAPH_VIEW = "feature.graph_view"
            MAX_STORAGE_BYTES = "limits.max_storage_bytes"
    """


class BooleanConfigValue(BaseModel):
    """Boolean configuration value (feature flags on/off)."""

    type: Literal["boolean"] = "boolean"
    value: bool


class IntegerConfigValue(BaseModel):
    """Integer configuration value with optional bounds."""

    type: Literal["integer"] = "integer"
    value: int
    min_value: int | None = None
    max_value: int | None = None


class FloatConfigValue(BaseModel):
    """Float configuration value with optional bounds."""

    type: Literal["float"] = "float"
    value: float
    min_value: float | None = None
    max_value: float | None = None


class StringConfigValue(BaseModel):
    """String configuration value with optional length constraint."""

    type: Literal["string"] = "string"
    value: str
    max_length: int | None = None


class PercentageConfigValue(BaseModel):
    """Percentage configuration value (0-100 for feature rollouts)."""

    type: Literal["percentage"] = "percentage"
    value: int = Field(ge=0, le=100)


class EnumConfigValue(BaseModel):
    """Enum configuration value (value must be in allowed set)."""

    type: Literal["enum"] = "enum"
    value: str
    allowed_values: list[str]


ConfigValue = Annotated[
    BooleanConfigValue
    | IntegerConfigValue
    | FloatConfigValue
    | StringConfigValue
    | PercentageConfigValue
    | EnumConfigValue,
    Field(discriminator="type"),
]
"""Discriminated union of all configuration value types.

Uses Pydantic 2.x ``discriminator="type"`` for zero-ambiguity deserialization.
The ``type`` field on each model variant acts as the discriminator.
"""
