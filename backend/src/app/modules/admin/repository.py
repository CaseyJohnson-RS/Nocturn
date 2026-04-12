import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.auth.models import User


class AdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        query = select(User)
        count_query = select(func.count(User.id))

        if search:
            pattern = f"%{search}%"
            search_filter = User.email.ilike(pattern) | User.nickname.ilike(pattern)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        query = query.order_by(User.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        users = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return users, total

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def set_active(self, user_id: uuid.UUID, is_active: bool) -> None:
        await self.db.execute(
            update(User).where(User.id == user_id).values(is_active=is_active)
        )

    async def set_role(self, user_id: uuid.UUID, role: str) -> None:
        await self.db.execute(
            update(User).where(User.id == user_id).values(role=role)
        )
