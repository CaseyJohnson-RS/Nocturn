import pytest
import uuid
from datetime import timedelta
from app.domain.models.user import User
from app.adapters.outbound.persistence.sqlalchemy.repositories.user import UserRepository
from app.adapters.outbound.persistence.sqlalchemy.repositories.email_verification_token import (
    EmailVerificationTokenRepository,
)
from app.domain.models.email_verification_token import EmailVerificationToken
from app.utils.security import hash_token
from app.utils.time import utc_now
from app.utils.security import generate_token


@pytest.mark.asyncio
async def test_save_and_get_token_with_user(async_session):
    # создаем пользователя
    user_repo = UserRepository(async_session)
    user = User.register(email="test@example.com", password="pwd", username="tester")
    await user_repo.save(user)

    # создаем токен
    token_repo = EmailVerificationTokenRepository(async_session)
    token_str = generate_token(6)
    token = EmailVerificationToken(
        id=uuid.uuid4(),
        token_hash=hash_token(token_str),
        user_id=user.id,
        expires_at=utc_now() + timedelta(minutes=5),
        used=False,
    )

    await token_repo.save(token)

    # проверяем получение
    fetched = await token_repo.get_token_by_string(token_str)
    assert fetched is not None
    assert fetched.user_id == user.id
    assert fetched.used is False


@pytest.mark.asyncio
async def test_update_token(async_session):
    # создаем пользователя
    user_repo = UserRepository(async_session)
    user = User.register(email="update@example.com", password="pwd", username="updater")
    await user_repo.save(user)

    # создаем токен
    token_repo = EmailVerificationTokenRepository(async_session)
    token_str = generate_token(6)
    token = EmailVerificationToken(
        id=uuid.uuid4(),
        token_hash=hash_token(token_str),
        user_id=user.id,
        expires_at=utc_now() + timedelta(minutes=5),
        used=False,
    )
    await token_repo.save(token)

    # обновляем токен (например, помечаем как использованный)
    token.mark_as_used()
    await token_repo.save(token)

    fetched = await token_repo.get_token_by_string(token_str)
    assert fetched.used is True


@pytest.mark.asyncio
async def test_delete_token(async_session):
    # создаем пользователя
    user_repo = UserRepository(async_session)
    user = User.register(email="delete@example.com", password="pwd", username="deleter")
    await user_repo.save(user)

    # создаем токен
    token_repo = EmailVerificationTokenRepository(async_session)
    token_str = generate_token(6)
    token = EmailVerificationToken(
        id=uuid.uuid4(),
        token_hash=hash_token(token_str),
        user_id=user.id,
        expires_at=utc_now() + timedelta(minutes=5),
        used=False,
    )
    await token_repo.save(token)

    # удаляем
    await token_repo.delete(token)

    fetched = await token_repo.get_token_by_string(token_str)
    assert fetched is None
