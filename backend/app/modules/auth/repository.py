import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken, User, VerificationToken


class AuthRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Users ---

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_by_nickname(self, nickname: str) -> User | None:
        result = await self.db.execute(select(User).where(User.nickname == nickname))
        return result.scalar_one_or_none()

    async def create_user(
        self, email: str, nickname: str, password_hash: str, role: str = "user"
    ) -> User:
        user = User(
            email=email.lower(),
            nickname=nickname,
            password_hash=password_hash,
            role=role,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def confirm_email(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(User).where(User.id == user_id).values(is_email_confirmed=True)
        )

    async def update_password(self, user_id: uuid.UUID, password_hash: str) -> None:
        await self.db.execute(
            update(User).where(User.id == user_id).values(password_hash=password_hash)
        )

    async def update_nickname(self, user_id: uuid.UUID, nickname: str) -> None:
        await self.db.execute(update(User).where(User.id == user_id).values(nickname=nickname))

    async def set_active(self, user_id: uuid.UUID, is_active: bool) -> None:
        await self.db.execute(update(User).where(User.id == user_id).values(is_active=is_active))

    # --- Refresh tokens ---

    async def create_refresh_token(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def delete_refresh_token(self, token_id: uuid.UUID) -> None:
        await self.db.execute(delete(RefreshToken).where(RefreshToken.id == token_id))

    async def delete_all_user_refresh_tokens(self, user_id: uuid.UUID) -> None:
        await self.db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))

    async def count_user_sessions(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        return len(result.scalars().all())

    # --- Verification tokens ---

    async def create_verification_token(
        self, user_id: uuid.UUID, type: str, token_hash: str, expires_at: datetime
    ) -> VerificationToken:
        token = VerificationToken(
            user_id=user_id,
            type=type,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_verification_token_by_hash(
        self, token_hash: str, type: str
    ) -> VerificationToken | None:
        result = await self.db.execute(
            select(VerificationToken).where(
                VerificationToken.token_hash == token_hash,
                VerificationToken.type == type,
            )
        )
        return result.scalar_one_or_none()

    async def delete_verification_token(self, token_id: uuid.UUID) -> None:
        await self.db.execute(delete(VerificationToken).where(VerificationToken.id == token_id))

    async def delete_user_verification_tokens(self, user_id: uuid.UUID, type: str) -> None:
        await self.db.execute(
            delete(VerificationToken).where(
                VerificationToken.user_id == user_id,
                VerificationToken.type == type,
            )
        )
