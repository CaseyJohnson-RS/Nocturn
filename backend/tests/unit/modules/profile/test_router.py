"""Unit tests for profile router."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.common.exceptions import ConflictError, UnauthorizedError, ValidationError
from src.app.middleware.auth import get_current_user
from src.app.modules.auth.schemas import UserResponse
from src.app.modules.profile.router import get_profile_service, router

NICKNAME = "/api/profile/nickname"
PASSWORD = "/api/profile/password"
DELETE = "/api/profile/delete_account"


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def mock_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def app(mock_service: AsyncMock, user_id: uuid.UUID) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_profile_service] = lambda: mock_service
    test_app.dependency_overrides[get_current_user] = lambda: MagicMock(id=user_id, role="user")
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# --- PUT /nickname ---


class TestUpdateNickname:
    @pytest.mark.anyio()
    async def test_success(
        self, client: AsyncClient, mock_service: AsyncMock, user_id: uuid.UUID,
    ) -> None:
        mock_service.update_nickname.return_value = UserResponse(
            id=user_id,
            email="u@example.com",
            nickname="newnick",
            role="user",
            is_email_confirmed=True,
            is_active=True,
            created_at=datetime.now(UTC),
        )

        resp = await client.put(NICKNAME, json={"nickname": "newnick"})

        assert resp.status_code == 200
        assert resp.json()["nickname"] == "newnick"
        mock_service.update_nickname.assert_called_once_with(user_id, "newnick")

    @pytest.mark.anyio()
    async def test_nickname_taken(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.update_nickname.side_effect = ConflictError("Nickname already taken")

        resp = await client.put(NICKNAME, json={"nickname": "taken"})

        assert resp.status_code == 409

    @pytest.mark.anyio()
    async def test_too_short(self, client: AsyncClient) -> None:
        resp = await client.put(NICKNAME, json={"nickname": "a"})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_too_long(self, client: AsyncClient) -> None:
        resp = await client.put(NICKNAME, json={"nickname": "a" * 33})

        assert resp.status_code == 422


# --- PUT /password ---


class TestChangePassword:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        resp = await client.put(PASSWORD, json={
            "current_password": "Current1pass",
            "new_password": "NewValid1pass",
        })

        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

    @pytest.mark.anyio()
    async def test_wrong_current_password(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.change_password.side_effect = UnauthorizedError("Incorrect current password")

        resp = await client.put(PASSWORD, json={
            "current_password": "Wrong1pass",
            "new_password": "NewValid1pass",
        })

        assert resp.status_code == 401

    @pytest.mark.anyio()
    async def test_weak_new_password(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.change_password.side_effect = ValidationError("weak")

        resp = await client.put(PASSWORD, json={
            "current_password": "Current1pass",
            "new_password": "weak1234",
        })

        assert resp.status_code == 400

    @pytest.mark.anyio()
    async def test_short_new_password_rejected(self, client: AsyncClient) -> None:
        resp = await client.put(PASSWORD, json={
            "current_password": "Current1pass",
            "new_password": "short",
        })

        assert resp.status_code == 422


# --- POST /delete_account ---


class TestDeleteAccount:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        resp = await client.post(DELETE, json={"password": "Current1pass"})

        assert resp.status_code == 204

    @pytest.mark.anyio()
    async def test_wrong_password(
        self, client: AsyncClient, mock_service: AsyncMock,
    ) -> None:
        mock_service.delete_account.side_effect = UnauthorizedError("Incorrect password")

        resp = await client.post(DELETE, json={"password": "Wrong1pass"})

        assert resp.status_code == 401