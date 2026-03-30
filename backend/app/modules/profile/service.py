import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import UserResponse
from app.modules.auth.service import _validate_password

ph = PasswordHasher()


class ProfileService:
    def __init__(self, db: AsyncSession):
        self.repo = AuthRepository(db)

    async def update_nickname(self, user_id: uuid.UUID, nickname: str) -> UserResponse:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        if user.nickname == nickname:
            return UserResponse.model_validate(user)

        existing = await self.repo.get_user_by_nickname(nickname)
        if existing:
            raise ConflictError("Nickname already taken")

        await self.repo.update_nickname(user_id, nickname)
        user = await self.repo.get_user_by_id(user_id)
        return UserResponse.model_validate(user)

    async def change_password(
        self, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> None:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        try:
            ph.verify(user.password_hash, current_password)
        except VerifyMismatchError:
            raise UnauthorizedError("Incorrect current password")

        _validate_password(new_password)
        new_hash = ph.hash(new_password)
        await self.repo.update_password(user_id, new_hash)
        # Revoke all sessions so user must re-login with new password
        await self.repo.delete_all_user_refresh_tokens(user_id)

    async def delete_account(self, user_id: uuid.UUID, password: str) -> None:
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        try:
            ph.verify(user.password_hash, password)
        except VerifyMismatchError:
            raise UnauthorizedError("Incorrect password")

        await self.repo.set_active(user_id, False)
        await self.repo.delete_all_user_refresh_tokens(user_id)
