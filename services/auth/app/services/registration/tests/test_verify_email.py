import pytest
from unittest.mock import AsyncMock
from datetime import timedelta
import uuid

from app.services.registration.service import RegistrationService
from app.services.registration.schemas import VerifyEmailRequest
from app.services.registration.dto import VerifyEmailResult
from app.models import User, EmailVerificationToken

from app.core.time import utc_now


@pytest.mark.asyncio
async def test_verify_email_success(uow_mock):
    # Мок токена и пользователя
    fake_user = User.create(email="test@example.com", password_hash="hash", username="test")
    fake_user.user_id = uuid.uuid4()
    fake_token = EmailVerificationToken.create(
        token_hash="hashed-token",
        user_id=fake_user.user_id,
        expires_at=utc_now() + timedelta(hours=1)
    )
    fake_token.user = fake_user

    uow_mock.email_tokens.get_token_by_hash = AsyncMock(return_value=fake_token)
    uow_mock.users.set_email_verified = AsyncMock()
    uow_mock.email_tokens.mark_token_used = AsyncMock()

    data = VerifyEmailRequest(
        email="test@example.com",
        token="plain-token"
    )

    result = await RegistrationService.verify_email(data)

    # Проверяем DTO
    assert isinstance(result, VerifyEmailResult)
    assert result.user_id == fake_user.user_id
    assert result.email == fake_user.email
    assert result.token_used is True

    # Проверяем вызовы зависимостей
    uow_mock.users.set_email_verified.assert_called_once_with(fake_user)
    uow_mock.email_tokens.mark_token_used.assert_called_once_with(fake_token)


@pytest.mark.asyncio
async def test_verify_email_invalid_token(uow_mock):
    uow_mock.email_tokens.get_token_by_hash = AsyncMock(return_value=None)

    data = VerifyEmailRequest(
        email="test@example.com",
        token="plain-token"
    )

    with pytest.raises(ValueError, match="Invalid or expired token"):
        await RegistrationService.verify_email(data)


@pytest.mark.asyncio
async def test_verify_email_expired_token(uow_mock):
    # Токен существует, но просрочен
    fake_user = User.create(email="test@example.com", password_hash="hash", username="test")
    fake_user.user_id = uuid.uuid4()
    fake_token = EmailVerificationToken.create(
        token_hash="hashed-token",
        user_id=fake_user.user_id,
        expires_at=utc_now() - timedelta(minutes=1)  # просрочен
    )
    fake_token.user = fake_user

    uow_mock.email_tokens.get_token_by_hash = AsyncMock(return_value=fake_token)

    data = VerifyEmailRequest(
        email="test@example.com",
        token="plain-token"
    )

    with pytest.raises(ValueError, match="Invalid or expired token"):
        await RegistrationService.verify_email(data)


@pytest.mark.asyncio
async def test_verify_email_email_mismatch(uow_mock):
    # Токен существует, но email другой
    fake_user = User.create(email="other@example.com", password_hash="hash", username="test")
    fake_user.user_id = uuid.uuid4()
    fake_token = EmailVerificationToken.create(
        token_hash="hashed-token",
        user_id=fake_user.user_id,
        expires_at=utc_now() + timedelta(hours=1)
    )
    fake_token.user = fake_user

    uow_mock.email_tokens.get_token_by_hash = AsyncMock(return_value=fake_token)

    data = VerifyEmailRequest(
        email="test@example.com",
        token="plain-token"
    )

    with pytest.raises(ValueError, match="Email does not match token"):
        await RegistrationService.verify_email(data)
