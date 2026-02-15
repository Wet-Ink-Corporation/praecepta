"""Unit tests for praecepta.infra.persistence.tenant_context."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from praecepta.foundation.application.context import (
    clear_request_context,
    set_request_context,
)
from praecepta.infra.persistence.tenant_context import (
    _set_tenant_context_on_begin,
    register_tenant_context_handler,
)


class TestSetTenantContextOnBegin:
    @pytest.mark.unit
    def test_sets_tenant_when_context_available(self) -> None:
        token = set_request_context(
            tenant_id="tenant-abc",
            user_id=uuid4(),
            correlation_id="corr-123",
        )
        try:
            mock_connection = MagicMock()
            _set_tenant_context_on_begin(
                session=MagicMock(spec=Session),
                transaction=MagicMock(),
                connection=mock_connection,
            )
            mock_connection.execute.assert_called_once()
            call_args = mock_connection.execute.call_args
            assert "set_config" in str(call_args[0][0])
            assert call_args[0][1] == {"tenant": "tenant-abc"}
        finally:
            clear_request_context(token)

    @pytest.mark.unit
    def test_skips_when_no_request_context(self) -> None:
        mock_connection = MagicMock()
        # No request context set -- should not raise
        _set_tenant_context_on_begin(
            session=MagicMock(spec=Session),
            transaction=MagicMock(),
            connection=mock_connection,
        )
        mock_connection.execute.assert_not_called()

    @pytest.mark.unit
    def test_skips_when_tenant_id_empty(self) -> None:
        token = set_request_context(
            tenant_id="",
            user_id=uuid4(),
            correlation_id="corr-123",
        )
        try:
            mock_connection = MagicMock()
            _set_tenant_context_on_begin(
                session=MagicMock(spec=Session),
                transaction=MagicMock(),
                connection=mock_connection,
            )
            mock_connection.execute.assert_not_called()
        finally:
            clear_request_context(token)


class TestRegisterTenantContextHandler:
    @pytest.mark.unit
    def test_registers_event_listener(self) -> None:
        with patch("praecepta.infra.persistence.tenant_context.event") as mock_event:
            register_tenant_context_handler()
            mock_event.listen.assert_called_once_with(
                Session, "after_begin", _set_tenant_context_on_begin
            )
