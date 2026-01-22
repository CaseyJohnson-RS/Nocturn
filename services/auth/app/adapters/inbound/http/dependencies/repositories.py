from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.persistence.sqlalchemy.repositories.user import UserRepository
from app.adapters.outbound.persistence.sqlalchemy.repositories.email_verification_token import EmailVerificationTokenRepository

from .db import get_session


def get_user_repo(session: AsyncSession = Depends(get_session)) -> UserRepository:
    return UserRepository(session)

def get_token_repo(session: AsyncSession = Depends(get_session)) -> EmailVerificationTokenRepository:
    return EmailVerificationTokenRepository(session)