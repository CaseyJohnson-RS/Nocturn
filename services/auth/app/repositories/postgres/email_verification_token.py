from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.email_verification_token import EmailVerificationToken

class EmailVerificationTokenRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, token: EmailVerificationToken) -> None:
        """You must be sure that token is not in DB!"""
        self.session.add(token)
    
    async def get_token_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        result = await self.session.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
            .options(selectinload(EmailVerificationToken.user))
        )
        return result.scalar_one_or_none()
    
    async def mark_token_used(self, token: EmailVerificationToken) -> None:
        """You must be sure that token is in DB!"""
        if token:
            token.used = True