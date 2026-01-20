import pytest

from app.models import User
from app.models.sent_email import SentEmail

from app.repositories.postgres.sent_email import SentEmailRepository


@pytest.mark.asyncio
async def test_add_email_outbox(async_session):
    repo = SentEmailRepository(async_session)
    
    # Создаём пользователя, нужен для внешнего ключа
    user = User.create(
        email="testuser@example.com",
        username="tester",
        password_hash="hashed"
    )
    async_session.add(user)
    await async_session.commit()
    
    # Создаём EmailOutbox
    email_outbox = SentEmail.create(
        user_id=user.user_id,
        email_type="welcome",
        email="recipient@example.com",
        payload={"key": "value"}
    )
    
    # Добавляем в репозиторий
    await repo.add(email_outbox)
    await async_session.commit()
    
    # Проверяем, что email сохранился
    saved_email = await async_session.get(SentEmail, email_outbox.id)
    assert saved_email is not None
    assert saved_email.user_id == user.user_id
    assert saved_email.email_type == "welcome"
    assert saved_email.email == "recipient@example.com"
    assert saved_email.payload == {"key": "value"}
    assert saved_email.sent_at is None
