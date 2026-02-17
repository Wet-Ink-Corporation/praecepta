"""Praecepta Foundation Domain -- pure Python domain primitives.

This package provides the foundational domain building blocks for DDD/ES
multi-tenant applications: identifiers, exceptions, events, aggregates,
value objects, configuration types, and port interfaces.
"""

from praecepta.foundation.domain.agent_value_objects import (
    DEFAULT_API_KEY_PREFIX,
    AgentStatus,
    AgentTypeId,
    APIKeyMetadata,
)
from praecepta.foundation.domain.aggregates import BaseAggregate
from praecepta.foundation.domain.config_defaults import SYSTEM_DEFAULTS
from praecepta.foundation.domain.config_value_objects import (
    BooleanConfigValue,
    ConfigKey,
    ConfigValue,
    EnumConfigValue,
    FloatConfigValue,
    IntegerConfigValue,
    PercentageConfigValue,
    StringConfigValue,
)
from praecepta.foundation.domain.events import BaseEvent
from praecepta.foundation.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    FeatureDisabledError,
    InvalidStateTransitionError,
    NotFoundError,
    ResourceLimitExceededError,
    ValidationError,
)
from praecepta.foundation.domain.identifiers import TenantId, UserId
from praecepta.foundation.domain.policy_types import PolicyType
from praecepta.foundation.domain.ports import APIKeyGeneratorPort, LLMServicePort
from praecepta.foundation.domain.principal import Principal, PrincipalType
from praecepta.foundation.domain.tenant_value_objects import (
    SuspensionCategory,
    TenantName,
    TenantSlug,
    TenantStatus,
)
from praecepta.foundation.domain.user_value_objects import (
    DisplayName,
    Email,
    OidcSub,
)

__all__ = [
    "DEFAULT_API_KEY_PREFIX",
    "SYSTEM_DEFAULTS",
    "APIKeyGeneratorPort",
    "APIKeyMetadata",
    "AgentStatus",
    "AgentTypeId",
    "AuthenticationError",
    "AuthorizationError",
    "BaseAggregate",
    "BaseEvent",
    "BooleanConfigValue",
    "ConfigKey",
    "ConfigValue",
    "ConflictError",
    "DisplayName",
    "DomainError",
    "Email",
    "EnumConfigValue",
    "FeatureDisabledError",
    "FloatConfigValue",
    "IntegerConfigValue",
    "InvalidStateTransitionError",
    "LLMServicePort",
    "NotFoundError",
    "OidcSub",
    "PercentageConfigValue",
    "PolicyType",
    "Principal",
    "PrincipalType",
    "ResourceLimitExceededError",
    "StringConfigValue",
    "SuspensionCategory",
    "TenantId",
    "TenantName",
    "TenantSlug",
    "TenantStatus",
    "UserId",
    "ValidationError",
]
