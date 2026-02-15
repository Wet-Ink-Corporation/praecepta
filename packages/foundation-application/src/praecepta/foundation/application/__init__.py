"""Praecepta Foundation Application — application layer patterns."""

from praecepta.foundation.application.config_service import TenantConfigService
from praecepta.foundation.application.context import (
    NoRequestContextError,
    RequestContext,
    clear_principal_context,
    clear_request_context,
    get_current_context,
    get_current_correlation_id,
    get_current_principal,
    get_current_tenant_id,
    get_current_user_id,
    get_optional_principal,
    set_principal_context,
    set_request_context,
)
from praecepta.foundation.application.contributions import (
    ErrorHandlerContribution,
    LifespanContribution,
    MiddlewareContribution,
)
from praecepta.foundation.application.discovery import (
    DiscoveredContribution,
    discover,
)
from praecepta.foundation.application.issue_api_key import (
    IssueAPIKeyCommand,
    IssueAPIKeyHandler,
)
from praecepta.foundation.application.policy_binding import (
    PolicyBindingService,
    PolicyResolution,
)
from praecepta.foundation.application.resource_limits import (
    ResourceLimitResult,
    ResourceLimitService,
)
from praecepta.foundation.application.rotate_api_key import (
    RotateAPIKeyCommand,
    RotateAPIKeyHandler,
    RotateAPIKeyResult,
)

__all__ = [
    "DiscoveredContribution",
    "ErrorHandlerContribution",
    "IssueAPIKeyCommand",
    "IssueAPIKeyHandler",
    "LifespanContribution",
    "MiddlewareContribution",
    "NoRequestContextError",
    "PolicyBindingService",
    "PolicyResolution",
    "RequestContext",
    "ResourceLimitResult",
    "ResourceLimitService",
    "RotateAPIKeyCommand",
    "RotateAPIKeyHandler",
    "RotateAPIKeyResult",
    "TenantConfigService",
    "clear_principal_context",
    "clear_request_context",
    "discover",
    "get_current_context",
    "get_current_correlation_id",
    "get_current_principal",
    "get_current_tenant_id",
    "get_current_user_id",
    "get_optional_principal",
    "set_principal_context",
    "set_request_context",
]
