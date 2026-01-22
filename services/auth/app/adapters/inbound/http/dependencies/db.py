from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.persistence.sqlalchemy.transaction import SQLAlchemyTransaction

from app.infrastructure.db.postgres import async_session_factory  # твоя фабрика сессий

async def get_session() -> AsyncSession:
    return async_session_factory()

def get_transaction(session: AsyncSession = Depends(get_session)) -> SQLAlchemyTransaction:
    return SQLAlchemyTransaction(session)