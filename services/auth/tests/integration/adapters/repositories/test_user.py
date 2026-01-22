import pytest

from app.adapters.outbound.persistence.sqlalchemy.repositories.user import UserRepository
from app.domain.models.user import User


@pytest.mark.asyncio
async def test_save_and_get_user(async_session):
    repo = UserRepository(async_session)
    user = User.register("a@b.com", "password", "user1")
    
    await repo.save(user)
    fetched = await repo.get_user_by_email("a@b.com")
    
    assert fetched is not None
    assert fetched.email == user.email
    assert fetched.username == user.username

@pytest.mark.asyncio
async def test_update_user(async_session):
    repo = UserRepository(async_session)
    user = User.register("b@b.com", "password", "oldname")
    await repo.save(user)
    
    user.username = "newname"
    await repo.save(user)
    
    fetched = await repo.get_user_by_email("b@b.com")
    assert fetched.username == "newname"

@pytest.mark.asyncio
async def test_delete_user(async_session):
    repo = UserRepository(async_session)
    user = User.register("c@b.com", "password", "userdel")
    await repo.save(user)
    
    await repo.delete(user)
    fetched = await repo.get_user_by_email("c@b.com")
    assert fetched is None

@pytest.mark.asyncio
async def test_get_nonexistent_user(async_session):
    repo = UserRepository(async_session)
    fetched = await repo.get_user_by_email("noone@b.com")
    assert fetched is None
