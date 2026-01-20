import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

from app.repositories.postgres import UserRepository


@pytest.mark.asyncio
async def test_add_and_get_user(async_session: AsyncSession):
    repo = UserRepository(async_session)

    user = User.create(
        email="test@example.com",
        username="tester",
        password_hash="hashedpassword"
    )
    await repo.add(user)
    await async_session.commit()

    fetched_user = await repo.get_user_by_email("test@example.com")
    assert fetched_user is not None
    assert fetched_user.email == "test@example.com"
    assert fetched_user.username == "tester"
    assert fetched_user.is_email_verified is False

@pytest.mark.asyncio
async def test_set_email_verified(async_session: AsyncSession):
    repo = UserRepository(async_session)

    user = User.create(
        email="verify@example.com",
        username="verifyuser",
        password_hash="hashedpassword"
    )
    await repo.add(user)
    await async_session.commit()

    fetched_user = await repo.get_user_by_email("verify@example.com")
    assert fetched_user.is_email_verified is False

    await repo.set_email_verified(fetched_user)
    await async_session.commit()

    updated_user = await repo.get_user_by_email("verify@example.com")
    assert updated_user.is_email_verified is True

@pytest.mark.asyncio
async def test_get_user_by_email_not_found(async_session: AsyncSession):
    repo = UserRepository(async_session)

    user = await repo.get_user_by_email("nonexistent@example.com")
    assert user is None
