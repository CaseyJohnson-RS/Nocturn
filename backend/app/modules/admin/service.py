import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ForbiddenError, NotFoundError
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import UserListItem, UserListResponse


class AdminService:
    def __init__(self, db: AsyncSession):
        self.repo = AdminRepository(db)

    async def list_users(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> UserListResponse:
        users, total = await self.repo.list_users(limit, offset, search)
        return UserListResponse(
            items=[UserListItem.model_validate(u) for u in users],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_user(self, user_id: uuid.UUID) -> UserListItem:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        return UserListItem.model_validate(user)

    async def set_active(
        self, admin_id: uuid.UUID, user_id: uuid.UUID, is_active: bool
    ) -> UserListItem:
        if admin_id == user_id:
            raise ForbiddenError("Cannot change your own active status")

        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        await self.repo.set_active(user_id, is_active)
        user = await self.repo.get_user_by_id(user_id)
        return UserListItem.model_validate(user)

    async def set_role(
        self, admin_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> UserListItem:
        if admin_id == user_id:
            raise ForbiddenError("Cannot change your own role")

        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        await self.repo.set_role(user_id, role)
        user = await self.repo.get_user_by_id(user_id)
        return UserListItem.model_validate(user)
