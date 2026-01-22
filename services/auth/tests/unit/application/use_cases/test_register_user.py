import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import timedelta

from app.application.use_cases.register_user import RegistrationService
from app.application.dto.register_user import RegisterUserInputDTO
from app.domain.models import User
from app.domain.exceptions import UserAlreadyExists

@pytest.mark.asyncio
async def test_register_new_user():
    tx = AsyncMock()
    users_repo = AsyncMock()
    email_tokens_repo = AsyncMock()
    config = MagicMock()

    config.get_email_token_length.return_value = 16
    config.get_email_token_expiry.return_value = timedelta(hours=1)

    users_repo.get_user_by_email.return_value = None

    service = RegistrationService(tx, users_repo, email_tokens_repo, config)

    data = RegisterUserInputDTO(email="a@b.com", password="password", username="u1")
    output = await service.register(data)

    # Проверяем DTO
    assert output.email == "a@b.com"
    assert output.verification_email_enqueued is True
    assert isinstance(output.id, uuid4().__class__)

    # Проверяем вызовы репозиториев
    users_repo.save.assert_awaited()
    email_tokens_repo.save.assert_awaited()

@pytest.mark.asyncio
async def test_register_existing_user_not_verified():
    tx = AsyncMock()
    user = User.register("a@b.com", "password", "oldname")
    user.is_email_verified = False

    users_repo = AsyncMock()
    users_repo.get_user_by_email.return_value = user
    email_tokens_repo = AsyncMock()
    config = MagicMock()
    config.get_email_token_length.return_value = 16
    config.get_email_token_expiry.return_value = timedelta(hours=1)

    service = RegistrationService(tx, users_repo, email_tokens_repo, config)
    data = RegisterUserInputDTO(email="a@b.com", password="newpassword", username="newname")
    _ = await service.register(data)

    # Проверка, что user обновлён
    assert user.username == "newname"

    users_repo.save.assert_awaited_with(user)
    email_tokens_repo.save.assert_awaited()

@pytest.mark.asyncio
async def test_register_existing_user_verified_raises():
    tx = AsyncMock()
    user = User.register("a@b.com", "password", "u1")
    user.is_email_verified = True

    users_repo = AsyncMock()
    users_repo.get_user_by_email.return_value = user
    email_tokens_repo = AsyncMock()
    config = MagicMock()
    config.get_email_token_length.return_value = 16
    config.get_email_token_expiry.return_value = timedelta(hours=1)

    service = RegistrationService(tx, users_repo, email_tokens_repo, config)
    data = RegisterUserInputDTO(email="a@b.com", password="password", username="u1")

    with pytest.raises(UserAlreadyExists):
        await service.register(data)
