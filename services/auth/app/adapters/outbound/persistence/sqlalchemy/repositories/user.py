from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.repositories import UserRepository as DomainUserRepository

from app.adapters.outbound.persistence.sqlalchemy.models import User as UserORM
from app.domain.models.user import User, UserStatus

from uuid import UUID


def orm2domain(user: UserORM | None) -> User | None:
    if not user:
        return None
    return User(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        username=user.username,
        status=UserStatus(user.status),
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )


def domain2orm(user: User | None) -> UserORM | None:
    if not user:
        return None
    return UserORM(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        username=user.username,
        status=user.status.value,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )


class UserRepository(DomainUserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(UserORM).where(UserORM.email == email)
        )
        return orm2domain(result.scalar_one_or_none())

    async def get_user_by_id(self, id: UUID) -> User | None:
        result = await self.session.execute(select(UserORM).where(UserORM.id == id))
        return orm2domain(result.scalar_one_or_none())

    async def save(self, user: User):
        orm_user = await self.session.get(UserORM, user.id)
        if orm_user:
            # Обновляем существующего
            orm_user.email = user.email
            orm_user.username = user.username
            orm_user.password_hash = user.password_hash
            orm_user.status = user.status.value
            orm_user.is_email_verified = user.is_email_verified
            orm_user.created_at = user.created_at
        else:
            # Добавляем нового
            orm_user = domain2orm(user)
            self.session.add(orm_user)

        await self.session.flush() 

    async def delete(self, user: User):
        orm_user = await self.session.get(UserORM, user.id)
        if orm_user:
            await self.session.delete(orm_user)
            await self.session.flush()
