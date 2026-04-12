"""Unit tests for admin router."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.app.common.exceptions import NotFoundError
from src.app.middleware.auth import require_admin
from src.app.modules.admin.router import get_admin_service, router
from src.app.modules.admin.schemas import UserListItem, UserListResponse

USERS = "/api/admin/users"


def _user_item(
    user_id: uuid.UUID | None = None,
    email: str = "u@example.com",
    nickname: str = "nick",
    role: str = "user",
    is_email_confirmed: bool = True,
    is_active: bool = True,
    created_at: datetime | None = None,
) -> UserListItem:
    return UserListItem(
        id=user_id or uuid.uuid4(),
        email=email,
        nickname=nickname,
        role=role,
        is_email_confirmed=is_email_confirmed,
        is_active=is_active,
        created_at=created_at or datetime.now(UTC),
    )


@pytest.fixture()
def admin_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def mock_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def app(mock_service: AsyncMock, admin_id: uuid.UUID) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_admin_service] = lambda: mock_service
    test_app.dependency_overrides[require_admin] = lambda: MagicMock(id=admin_id, role="admin")
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# --- GET /users ---


class TestListUsers:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list_users.return_value = UserListResponse(
            items=[_user_item()],
            total=1,
            limit=50,
            offset=0,
        )

        resp = await client.get(USERS)

        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert len(resp.json()["items"]) == 1

    @pytest.mark.anyio()
    async def test_with_search(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list_users.return_value = UserListResponse(
            items=[],
            total=0,
            limit=50,
            offset=0,
        )

        resp = await client.get(USERS, params={"search": "test"})

        assert resp.status_code == 200
        mock_service.list_users.assert_called_once_with(50, 0, "test")

    @pytest.mark.anyio()
    async def test_pagination_params(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.list_users.return_value = UserListResponse(
            items=[],
            total=0,
            limit=10,
            offset=20,
        )

        resp = await client.get(USERS, params={"limit": 10, "offset": 20})

        assert resp.status_code == 200
        mock_service.list_users.assert_called_once_with(10, 20, None)

    @pytest.mark.anyio()
    async def test_limit_too_high(self, client: AsyncClient) -> None:
        resp = await client.get(USERS, params={"limit": 200})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_negative_offset(self, client: AsyncClient) -> None:
        resp = await client.get(USERS, params={"offset": -1})

        assert resp.status_code == 422


# --- GET /users/{user_id} ---


class TestGetUser:
    @pytest.mark.anyio()
    async def test_success(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        uid = uuid.uuid4()
        mock_service.get_user.return_value = _user_item(uid)

        resp = await client.get(f"{USERS}/{uid}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(uid)

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.get_user.side_effect = NotFoundError("User not found")

        resp = await client.get(f"{USERS}/{uuid.uuid4()}")

        assert resp.status_code == 404


# --- PUT /users/{user_id}/active ---


class TestSetActive:
    @pytest.mark.anyio()
    async def test_deactivate(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        uid = uuid.uuid4()
        mock_service.set_active.return_value = _user_item(uid, is_active=False)

        resp = await client.put(f"{USERS}/{uid}/active", json={"is_active": False})

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        mock_service.set_active.assert_called_once_with(admin_id, uid, False)

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.set_active.side_effect = NotFoundError("User not found")

        resp = await client.put(f"{USERS}/{uuid.uuid4()}/active", json={"is_active": False})

        assert resp.status_code == 404


# --- PUT /users/{user_id}/role ---


class TestSetRole:
    @pytest.mark.anyio()
    async def test_promote_to_admin(
        self,
        client: AsyncClient,
        mock_service: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        uid = uuid.uuid4()
        mock_service.set_role.return_value = _user_item(uid, role="admin")

        resp = await client.put(f"{USERS}/{uid}/role", json={"role": "admin"})

        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"
        mock_service.set_role.assert_called_once_with(admin_id, uid, "admin")

    @pytest.mark.anyio()
    async def test_invalid_role(self, client: AsyncClient) -> None:
        resp = await client.put(f"{USERS}/{uuid.uuid4()}/role", json={"role": "superadmin"})

        assert resp.status_code == 422

    @pytest.mark.anyio()
    async def test_not_found(self, client: AsyncClient, mock_service: AsyncMock) -> None:
        mock_service.set_role.side_effect = NotFoundError("User not found")

        resp = await client.put(f"{USERS}/{uuid.uuid4()}/role", json={"role": "admin"})

        assert resp.status_code == 404
