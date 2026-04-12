"""Integration tests for auth router."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.common.exceptions import NotFoundError, UnauthorizedError, ValidationError
from src.app.modules.auth.router import get_auth_service, router
from src.app.modules.auth.schemas import TokenResponse

REFRESH_COOKIE = "refresh_token"


@pytest.fixture()
def mock_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def app(mock_service: AsyncMock) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_auth_service] = lambda: mock_service
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# --- POST /register ---


class TestRegister:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.register.return_value = "Confirmation link sent"

        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "u@example.com",
                "password": "Valid1pass",
                "nickname": "nick",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Confirmation link sent"

    @pytest.mark.anyio()
    async def test_short_password_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "u@example.com",
                "password": "short",
                "nickname": "nick",
            },
        )

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_invalid_email_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "Valid1pass",
                "nickname": "nick",
            },
        )

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_short_nickname_rejected(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "u@example.com",
                "password": "Valid1pass",
                "nickname": "a",
            },
        )

        assert resp.status_code == 422


# --- POST /login ---


class TestLogin:
    @pytest.mark.anyio()
    async def test_success_sets_cookie(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.login.return_value = (
            TokenResponse(access_token="access-tok"),
            "refresh-tok",
        )

        resp = await client.post(
            "/api/auth/login",
            json={
                "email": "u@example.com",
                "password": "Valid1pass",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["access_token"] == "access-tok"
        assert REFRESH_COOKIE in resp.cookies

    @pytest.mark.anyio()
    async def test_invalid_credentials(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.login.side_effect = UnauthorizedError("Invalid credentials")

        resp = await client.post(
            "/api/auth/login",
            json={
                "email": "u@example.com",
                "password": "Wrong1pass",
            },
        )

        assert resp.status_code == 401


# --- POST /refresh ---


class TestRefresh:
    @pytest.mark.anyio()
    async def test_success_rotates_cookie(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
    ) -> None:
        # Arrange
        client.cookies.set(REFRESH_COOKIE, "old-refresh")
        mock_service.refresh.return_value = (
            TokenResponse(access_token="new-access"),
            "new-refresh",
        )

        # Act
        resp = await client.post("/api/auth/refresh")

        # Assert
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "new-access"
        assert REFRESH_COOKIE in resp.cookies
        mock_service.refresh.assert_awaited_once_with("old-refresh")

        # Cleanup
        client.cookies.clear()

    @pytest.mark.anyio()
    async def test_no_cookie_returns_401(self, client: AsyncClient) -> None:
        resp = await client.post("/api/auth/refresh")

        assert resp.status_code == 401


# --- POST /logout ---


class TestLogout:
    @pytest.mark.anyio()
    async def test_with_cookie(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
    ) -> None:
        # Arrange
        client.cookies.set(REFRESH_COOKIE, "some-token")

        # Act
        resp = await client.post("/api/auth/logout")

        # Assert
        assert resp.status_code == 200
        mock_service.logout.assert_awaited_once_with("some-token")

        # Cleanup (important if client fixture is shared)
        client.cookies.clear()

    @pytest.mark.anyio()
    async def test_without_cookie(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        resp = await client.post("/api/auth/logout")

        assert resp.status_code == 200
        mock_service.logout.assert_not_called()


# --- POST /confirm-email ---


class TestConfirmEmail:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        resp = await client.post("/api/auth/confirm-email", json={"token": "tok"})

        assert resp.status_code == 200
        mock_service.confirm_email.assert_called_once_with("tok")

    @pytest.mark.anyio()
    async def test_invalid_token(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.confirm_email.side_effect = NotFoundError("Invalid")

        resp = await client.post("/api/auth/confirm-email", json={"token": "bad"})

        assert resp.status_code == 404


# --- POST /request-password-reset ---


class TestRequestPasswordReset:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.request_password_reset.return_value = "If registered, link sent"

        resp = await client.post(
            "/api/auth/request-password-reset",
            json={
                "email": "u@example.com",
            },
        )

        assert resp.status_code == 200

    @pytest.mark.anyio()
    async def test_invalid_email(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/request-password-reset",
            json={
                "email": "bad",
            },
        )

        assert resp.status_code == 422


# --- POST /reset-password ---


class TestResetPassword:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        resp = await client.post(
            "/api/auth/reset-password",
            json={
                "token": "tok",
                "new_password": "NewValid1",
            },
        )

        assert resp.status_code == 200
        mock_service.reset_password.assert_called_once_with("tok", "NewValid1")

    @pytest.mark.anyio()
    async def test_weak_password(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.reset_password.side_effect = ValidationError("weak")

        resp = await client.post(
            "/api/auth/reset-password",
            json={
                "token": "tok",
                "new_password": "weak1234",
            },
        )

        assert resp.status_code == 400


# --- POST /resend-confirmation ---


class TestResendConfirmation:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.resend_confirmation.return_value = "If not confirmed, link sent"

        resp = await client.post(
            "/api/auth/resend-confirmation",
            json={
                "email": "u@example.com",
            },
        )

        assert resp.status_code == 200


# --- GET /me ---


class TestGetMe:
    @pytest.mark.anyio()
    async def test_success(
        self, client: AsyncClient, mock_service: AsyncMock, app: FastAPI
    ) -> None:
        user_id = uuid.uuid4()
        mock_service.get_user.return_value = MagicMock(
            id=user_id,
            email="u@example.com",
            nickname="nick",
            role="user",
            is_email_confirmed=True,
            is_active=True,
            created_at=datetime.now(UTC),
        )

        # Override auth dependency to inject a fake user
        from src.app.middleware.auth import get_current_user

        app.dependency_overrides[get_current_user] = lambda: MagicMock(
            id=user_id, role="user"
        )

        try:
            resp = await client.get("/api/auth/me")

            assert resp.status_code == 200
            assert resp.json()["email"] == "u@example.com"
        finally:
            # Cleanup: remove the override
            app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.anyio()
    async def test_unauthorized(self, client: AsyncClient) -> None:
        resp = await client.get("/api/auth/me")

        assert resp.status_code in (401, 403)
