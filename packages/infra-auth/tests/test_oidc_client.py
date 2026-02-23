"""Tests for OIDCTokenClient: token exchange, refresh, revoke, error handling."""

from __future__ import annotations

import httpx
import pytest

from praecepta.infra.auth.oidc_client import (
    OIDCTokenClient,
    TokenExchangeError,
)


@pytest.mark.unit
class TestOIDCTokenClient:
    """Test OIDCTokenClient with mocked httpx."""

    @pytest.fixture()
    def client(self) -> OIDCTokenClient:
        return OIDCTokenClient(
            base_url="https://auth.example.com",
            client_id="test-client-id",
            client_secret="test-client-secret",
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_exchange_code_success(
        self, client: OIDCTokenClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_post(self_client: httpx.AsyncClient, *args, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(
                200,
                json={
                    "access_token": "at_123",
                    "refresh_token": "rt_456",
                    "id_token": "idt_789",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "userId": "user-uuid",
                },
                request=httpx.Request("POST", "https://auth.example.com/oauth2/token"),
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        token_resp = await client.exchange_code(
            code="auth_code",
            code_verifier="verifier",
            redirect_uri="http://localhost/cb",
        )

        assert token_resp.access_token == "at_123"
        assert token_resp.refresh_token == "rt_456"
        assert token_resp.id_token == "idt_789"
        assert token_resp.expires_in == 3600
        assert token_resp.token_type == "Bearer"
        assert token_resp.user_id == "user-uuid"

    @pytest.mark.asyncio
    async def test_exchange_code_error_raises(
        self, client: OIDCTokenClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_post(self_client: httpx.AsyncClient, *args, **kwargs):  # type: ignore[no-untyped-def]
            resp = httpx.Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "Code has expired",
                },
                request=httpx.Request("POST", "https://auth.example.com/oauth2/token"),
            )
            resp.raise_for_status()
            return resp  # pragma: no cover

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        with pytest.raises(TokenExchangeError) as exc_info:
            await client.exchange_code(
                code="bad_code",
                code_verifier="verifier",
                redirect_uri="http://localhost/cb",
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.error == "invalid_grant"

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, client: OIDCTokenClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_post(self_client: httpx.AsyncClient, *args, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(
                200,
                json={
                    "access_token": "at_new",
                    "refresh_token": "rt_rotated",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
                request=httpx.Request("POST", "https://auth.example.com/oauth2/token"),
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        token_resp = await client.refresh_token("old_refresh_token")
        assert token_resp.access_token == "at_new"
        assert token_resp.refresh_token == "rt_rotated"

    @pytest.mark.asyncio
    async def test_revoke_token_success(
        self, client: OIDCTokenClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_post(self_client: httpx.AsyncClient, *args, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(
                200,
                request=httpx.Request("POST", "https://auth.example.com/oauth2/revoke"),
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        # Should not raise
        await client.revoke_token("some_refresh_token")

    @pytest.mark.asyncio
    async def test_revoke_token_failure_does_not_raise(
        self, client: OIDCTokenClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def mock_post(self_client: httpx.AsyncClient, *args, **kwargs):  # type: ignore[no-untyped-def]
            resp = httpx.Response(
                500,
                request=httpx.Request("POST", "https://auth.example.com/oauth2/revoke"),
            )
            resp.raise_for_status()
            return resp  # pragma: no cover

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

        # Revocation is best-effort; should not raise
        await client.revoke_token("some_refresh_token")

    @pytest.mark.asyncio
    async def test_shared_client_reused_across_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two calls should reuse the same internal httpx.AsyncClient."""
        shared = httpx.AsyncClient()
        oidc = OIDCTokenClient(
            base_url="https://auth.example.com",
            client_id="cid",
            client_secret="csec",
            client=shared,
        )
        # Internal client should be the one we passed
        assert oidc._get_client() is shared

        # aclose should NOT close an externally-provided client
        await oidc.aclose()
        assert oidc._client is shared
        await shared.aclose()

    @pytest.mark.asyncio
    async def test_lazy_client_created_on_first_use(self) -> None:
        """Without explicit client, one is created lazily."""
        oidc = OIDCTokenClient(
            base_url="https://auth.example.com",
            client_id="cid",
            client_secret="csec",
        )
        assert oidc._client is None
        client = oidc._get_client()
        assert client is not None
        # Same instance returned on second call
        assert oidc._get_client() is client
        await oidc.aclose()
        assert oidc._client is None
