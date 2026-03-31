import uuid

from sqlalchemy import delete, func, select, update
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
        actions: dict | list | None = None,
        attached_note_ids: list[uuid.UUID] | None = None,
        token_estimate: int = 0,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
            actions=actions,
            attached_note_ids=attached_note_ids,
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

    async def get_message(
        self, message_id: uuid.UUID, session_id: uuid.UUID,
    ) -> ChatMessage | None:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.id == message_id, ChatMessage.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def update_message_actions(
        self,
        message: ChatMessage,
        actions: dict | list | None,
    ) -> ChatMessage:
        await self.db.execute(
            update(ChatMessage)
            .where(ChatMessage.id == message.id)
            .values(actions=actions)
        )
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def find_action_by_id(
        self,
        session_id: uuid.UUID,
        action_id: str,
    ) -> tuple[ChatMessage | None, dict | None]:
        """Find an action (proposal or pending_confirmation) by its UUID
        across all messages in a session. Returns (message, action_dict)."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "assistant",
                ChatMessage.actions.is_not(None),
            )
            .order_by(ChatMessage.created_at.desc())
        )
        messages = result.scalars().all()

        for msg in messages:
            actions = msg.actions
            if isinstance(actions, dict):
                actions = [actions]
            if not isinstance(actions, list):
                continue
            for a in actions:
                if isinstance(a, dict) and a.get("id") == action_id:
                    return msg, a

        return None, None
