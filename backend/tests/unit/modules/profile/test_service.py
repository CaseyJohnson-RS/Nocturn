"""Unit tests for ProfileService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from argon2 import PasswordHasher

from app.common.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.modules.profile.service import ProfileService

ph = PasswordHasher()


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock) -> ProfileService:
    svc = ProfileService.__new__(ProfileService)
    svc.repo = repo
    return svc


@pytest.fixture()
def user() -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.email = "user@example.com"
    u.nickname = "oldnick"
    u.role = "user"
    u.is_email_confirmed = True
    u.is_active = True
    u.password_hash = ph.hash("Current1pass")
    return u


# --- update_nickname ---


class TestUpdateNickname:
    @pytest.mark.anyio()
    async def test_success(self, service: ProfileService, repo: AsyncMock, user: MagicMock) -> None:
        updated = MagicMock()
        updated.id = user.id
        updated.email = user.email
        updated.nickname = "newnick"
        updated.role = user.role
        updated.is_email_confirmed = user.is_email_confirmed
        updated.is_active = user.is_active
        updated.created_at = user.created_at

        repo.get_user_by_id.side_effect = [user, updated]
        repo.get_user_by_nickname.return_value = None

        result = await service.update_nickname(user.id, "newnick")

        repo.update_nickname.assert_called_once_with(user.id, "newnick")
        assert result.nickname == "newnick"

    @pytest.mark.anyio()
    async def test_same_nickname_skips_update(
        self, service: ProfileService, repo: AsyncMock, user: MagicMock,
    ) -> None:
        repo.get_user_by_id.return_value = user

        await service.update_nickname(user.id, "oldnick")

        repo.update_nickname.assert_not_called()
        repo.get_user_by_nickname.assert_not_called()

    @pytest.mark.anyio()
    async def test_nickname_taken(
        self, service: ProfileService, repo: AsyncMock, user: MagicMock,
    ) -> None:
        repo.get_user_by_id.return_value = user
        repo.get_user_by_nickname.return_value = MagicMock()  # someone else

        with pytest.raises(ConflictError, match="taken"):
            await service.update_nickname(user.id, "takennick")

    @pytest.mark.anyio()
    async def test_user_not_found(self, service: ProfileService, repo: AsyncMock) -> None:
        repo.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.update_nickname(uuid.uuid4(), "nick")


# --- change_password ---


class TestChangePassword:
    @pytest.mark.anyio()
    async def test_success(self, service: ProfileService, repo: AsyncMock, user: MagicMock) -> None:
        repo.get_user_by_id.return_value = user

        await service.change_password(user.id, "Current1pass", "NewValid1pass")

        repo.update_password.assert_called_once()
        repo.delete_all_user_refresh_tokens.assert_called_once_with(user.id)

    @pytest.mark.anyio()
    async def test_wrong_current_password(
        self, service: ProfileService, repo: AsyncMock, user: MagicMock,
    ) -> None:
        repo.get_user_by_id.return_value = user

        with pytest.raises(UnauthorizedError, match="Incorrect"):
            await service.change_password(user.id, "Wrong1pass", "NewValid1pass")

    @pytest.mark.anyio()
    async def test_weak_new_password(
        self, service: ProfileService, repo: AsyncMock, user: MagicMock,
    ) -> None:
        repo.get_user_by_id.return_value = user

        with pytest.raises(ValidationError):
            await service.change_password(user.id, "Current1pass", "weak")

    @pytest.mark.anyio()
    async def test_user_not_found(self, service: ProfileService, repo: AsyncMock) -> None:
        repo.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.change_password(uuid.uuid4(), "Any1pass", "New1pass")


# --- delete_account ---


class TestDeleteAccount:
    @pytest.mark.anyio()
    async def test_success(self, service: ProfileService, repo: AsyncMock, user: MagicMock) -> None:
        repo.get_user_by_id.return_value = user

        await service.delete_account(user.id, "Current1pass")

        repo.set_active.assert_called_once_with(user.id, False)
        repo.delete_all_user_refresh_tokens.assert_called_once_with(user.id)

    @pytest.mark.anyio()
    async def test_wrong_password(
        self, service: ProfileService, repo: AsyncMock, user: MagicMock,
    ) -> None:
        repo.get_user_by_id.return_value = user

        with pytest.raises(UnauthorizedError, match="Incorrect"):
            await service.delete_account(user.id, "Wrong1pass")

        repo.set_active.assert_not_called()

    @pytest.mark.anyio()
    async def test_user_not_found(self, service: ProfileService, repo: AsyncMock) -> None:
        repo.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.delete_account(uuid.uuid4(), "Any1pass")