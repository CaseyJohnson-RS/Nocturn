import pytest
from unittest.mock import AsyncMock, MagicMock

import uuid

from app.services.registration.service import RegistrationService
from app.services.registration.schemas import RegisterUserSchema
from app.services.registration.dto import RegistrationResult
from app.services.registration.exceptions import UserAlreadyExists


@pytest.mark.asyncio
async def test_register_user_success(uow_mock, monkeypatch):
    # Моки UoW
    uow_mock.users.get_user_by_email = AsyncMock(return_value=None)
    uow_mock.users.add = AsyncMock()
    uow_mock.email_tokens.add = AsyncMock()
    uow_mock.email_outbox = MagicMock()

    # Мок EmailFactory
    monkeypatch.setattr(
        "app.services.registration.service.EmailOutboxCreator.verification_email",
        AsyncMock()
    )

    data = RegisterUserSchema(
        email="test@example.com",
        username="test",
        password="password123"
    )

    # Вызов метода
    result = await RegistrationService.register_user(data)

    # Проверяем DTO
    assert isinstance(result, RegistrationResult)
    assert result.email == data.email
    assert result.verification_email_enqueued is True
    assert isinstance(result.user_id, uuid.UUID)

    # Проверяем вызовы зависимостей
    uow_mock.users.get_user_by_email.assert_called_once_with(data.email)
    uow_mock.users.add.assert_called_once()
    uow_mock.email_tokens.add.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_already_exists(uow_mock):
    # Пользователь уже существует
    uow_mock.users.get_user_by_email = AsyncMock(return_value=object())

    data = RegisterUserSchema(
        email="test@example.com",
        username="test",
        password="password123"
    )

    with pytest.raises(UserAlreadyExists):
        await RegistrationService.register_user(data)
