from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.persistence.sqlalchemy.models import (
    EmailVerificationToken as EmailVerificationTokenORM,
)
from app.domain.models.email_verification_token import EmailVerificationToken
from app.domain.ports.repositories import EmailVerificationTokenRepository as DomainEmailVerificationTokenRepository
from app.utils.security import hash_token


def orm2domain(
    token: EmailVerificationTokenORM | None,
) -> EmailVerificationToken | None:
    if not token:
        return None

    return EmailVerificationToken(
        id=token.id,
        token_hash=token.token_hash,
        expires_at=token.expires_at,
        used=token.used,
        user_id=token.user_id
    )


def domain2orm(
    token: EmailVerificationToken | None,
) -> EmailVerificationTokenORM | None:
    if not token:
        return None

    return EmailVerificationTokenORM(
        id=token.id,
        token_hash=token.token_hash,
        user_id=token.user_id,
        expires_at=token.expires_at,
        used=token.used,
    )


class EmailVerificationTokenRepository(DomainEmailVerificationTokenRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_token_by_string(self, token_string: str) -> EmailVerificationToken | None:
        result = await self.session.execute(
            select(EmailVerificationTokenORM)
            .where(EmailVerificationTokenORM.token_hash == hash_token(token_string))
            .options(selectinload(EmailVerificationTokenORM.user))
        )
        return orm2domain(result.scalar_one_or_none())

    async def save(self, token: EmailVerificationToken):
        orm_token = await self.session.get(EmailVerificationTokenORM, token.id)
        if orm_token:
            # обновляем существующий
            orm_token.token_hash = token.token_hash
            orm_token.user_id = token.user_id
            orm_token.expires_at = token.expires_at
            orm_token.used = token.used
        else:
            # создаем новый
            orm_token = domain2orm(token)
            self.session.add(orm_token)

        await self.session.flush()  # commit контролируется сверху транзакцией

    async def delete(self, token: EmailVerificationToken):
        orm_token = await self.session.get(EmailVerificationTokenORM, token.id)
        if orm_token:
            await self.session.delete(orm_token)
            await self.session.flush()
