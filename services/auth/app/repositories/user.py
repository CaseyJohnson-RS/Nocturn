from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

class UserRepository:

    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def set_email_verified(self, user: User):
        if user:
            user.is_email_verified = True

    async def add(self, user: User):
        self.session.add(user)