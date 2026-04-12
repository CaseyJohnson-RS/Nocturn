"""Unit tests for AdminService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.common.exceptions import ForbiddenError, NotFoundError
from src.app.modules.admin.service import AdminService


def _mock_user(
    user_id: uuid.UUID | None = None,
    email: str = "u@example.com",
    nickname: str = "nick",
    role: str = "user",
    is_email_confirmed: bool = True,
    is_active: bool = True,
) -> MagicMock:
    u = MagicMock()
    u.id = user_id or uuid.uuid4()
    u.email = email
    u.nickname = nickname
    u.role = role
    u.is_email_confirmed = is_email_confirmed
    u.is_active = is_active
    u.created_at = datetime.now(UTC)
    return u


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock) -> AdminService:
    svc = AdminService.__new__(AdminService)
    svc.repo = repo
    return svc


@pytest.fixture()
def admin_id() -> uuid.UUID:
    return uuid.uuid4()


# --- list_users ---


class TestListUsers:
    @pytest.mark.anyio()
    async def test_returns_users(self, service: AdminService, repo: AsyncMock) -> None:
        users = [_mock_user(), _mock_user()]
        repo.list_users.return_value = (users, 2)

        result = await service.list_users(limit=50, offset=0)

        assert result.total == 2
        assert len(result.items) == 2
        repo.list_users.assert_called_once_with(50, 0, None)

    @pytest.mark.anyio()
    async def test_with_search(self, service: AdminService, repo: AsyncMock) -> None:
        repo.list_users.return_value = ([], 0)

        result = await service.list_users(limit=10, offset=5, search="test")

        assert result.total == 0
        assert result.limit == 10
        assert result.offset == 5
        repo.list_users.assert_called_once_with(10, 5, "test")

    @pytest.mark.anyio()
    async def test_empty(self, service: AdminService, repo: AsyncMock) -> None:
        repo.list_users.return_value = ([], 0)

        result = await service.list_users()

        assert result.items == []
        assert result.total == 0


# --- get_user ---


class TestGetUser:
    @pytest.mark.anyio()
    async def test_found(self, service: AdminService, repo: AsyncMock) -> None:
        uid = uuid.uuid4()
        repo.get_user_by_id.return_value = _mock_user(user_id=uid, email="found@example.com")

        result = await service.get_user(uid)

        assert result.id == uid
        assert result.email == "found@example.com"

    @pytest.mark.anyio()
    async def test_not_found(self, service: AdminService, repo: AsyncMock) -> None:
        repo.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.get_user(uuid.uuid4())


# --- set_active ---


class TestSetActive:
    @pytest.mark.anyio()
    async def test_deactivate(
        self,
        service: AdminService,
        repo: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        uid = uuid.uuid4()
        user = _mock_user(user_id=uid)
        deactivated = _mock_user(user_id=uid, is_active=False)
        repo.get_user_by_id.side_effect = [user, deactivated]

        result = await service.set_active(admin_id, uid, False)

        assert result.is_active is False
        repo.set_active.assert_called_once_with(uid, False)

    @pytest.mark.anyio()
    async def test_cannot_deactivate_self(
        self,
        service: AdminService,
        repo: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        with pytest.raises(ForbiddenError, match="own"):
            await service.set_active(admin_id, admin_id, False)

        repo.set_active.assert_not_called()

    @pytest.mark.anyio()
    async def test_user_not_found(
        self,
        service: AdminService,
        repo: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        repo.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.set_active(admin_id, uuid.uuid4(), False)


# --- set_role ---


class TestSetRole:
    @pytest.mark.anyio()
    async def test_promote_to_admin(
        self,
        service: AdminService,
        repo: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        uid = uuid.uuid4()
        user = _mock_user(user_id=uid)
        promoted = _mock_user(user_id=uid, role="admin")
        repo.get_user_by_id.side_effect = [user, promoted]

        result = await service.set_role(admin_id, uid, "admin")

        assert result.role == "admin"
        repo.set_role.assert_called_once_with(uid, "admin")

    @pytest.mark.anyio()
    async def test_cannot_change_own_role(
        self,
        service: AdminService,
        repo: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        with pytest.raises(ForbiddenError, match="own"):
            await service.set_role(admin_id, admin_id, "user")

        repo.set_role.assert_not_called()

    @pytest.mark.anyio()
    async def test_user_not_found(
        self,
        service: AdminService,
        repo: AsyncMock,
        admin_id: uuid.UUID,
    ) -> None:
        repo.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.set_role(admin_id, uuid.uuid4(), "admin")
