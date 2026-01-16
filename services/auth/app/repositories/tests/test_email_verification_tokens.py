import pytest
from datetime import timedelta

from app.core.time import utc_now

from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User

from app.repositories import EmailVerificationTokenRepository


@pytest.mark.asyncio
async def test_add_and_get_token(async_session):
    repo = EmailVerificationTokenRepository(async_session)
    
    # Создаём пользователя и токен
    user = User.create(
        email="test@example.com",
        username="tester",
        password_hash="hashed"
    )
    token = EmailVerificationToken.create(
        token_hash="abc123",
        user_id=user.user_id,
        expires_at=utc_now() + timedelta(hours=1)
    )
    
    async_session.add(user)
    await repo.add(token)
    await async_session.commit()
    
    # Получаем токен по хэшу
    fetched = await repo.get_token_by_hash("abc123")
    assert fetched is not None
    assert fetched.token_hash == "abc123"
    assert fetched.user.user_id == user.user_id

@pytest.mark.asyncio
async def test_get_token_returns_none(async_session):
    repo = EmailVerificationTokenRepository(async_session)
    
    # Попытка получить несуществующий токен
    fetched = await repo.get_token_by_hash("nonexistent")
    assert fetched is None

@pytest.mark.asyncio
async def test_mark_token_used(async_session):
    repo = EmailVerificationTokenRepository(async_session)
    
    user = User.create(
        email="test@example.com",
        username="tester",
        password_hash="hashed"
    )
    token = EmailVerificationToken.create(
        token_hash="xyz789",
        user_id=user.user_id,
        expires_at=utc_now() + timedelta(hours=1)
    )

    async_session.add(user)
    await repo.add(token)
    await async_session.commit()
    
    # Помечаем токен как использованный
    await repo.mark_token_used(token)
    await async_session.commit()
    
    fetched = await repo.get_token_by_hash("xyz789")
    assert fetched.used is True
