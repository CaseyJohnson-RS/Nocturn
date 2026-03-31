import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ai.models import ChatMessage, ChatSession


class AIRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Sessions ---

    async def create_session(
        self, user_id: uuid.UUID, title: str | None = None,
    ) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title)
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID,
    ) -> ChatSession | None:
        result = await self.db.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0,
    ) -> tuple[list[ChatSession], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def update_session_title(
        self, session: ChatSession, title: str,
    ) -> ChatSession:
        session.title = title
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def delete_session(self, session: ChatSession) -> None:
        await self.db.delete(session)
        await self.db.flush()

    async def count_user_sessions(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
        )
        return result.scalar_one()

    # --- Messages ---

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sources: str | None = None,
        token_estimate: int = 0,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
            token_estimate=token_estimate,
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def get_recent_messages(
        self, session_id: uuid.UUID, limit: int = 25,
    ) -> list[ChatMessage]:
        """Get the most recent messages for context, ordered chronologically."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # chronological order
        return messages
