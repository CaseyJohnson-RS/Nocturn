import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.modules.ai.models import ChatMessage, ChatSession


class AIRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Sessions ---

    async def create_session(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title)
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ChatSession | None:
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user_id),
        )
        return result.scalar_one_or_none()

    async def get_session_with_messages(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ChatSession | None:
        result = await self.db.execute(
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id),
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChatSession], int]:
        count_result = await self.db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id),
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(
                ChatSession.last_message_at.desc().nulls_last(), ChatSession.created_at.desc()
            )
            .limit(limit)
            .offset(offset),
        )
        return list(result.scalars().all()), total

    async def update_session_title(
        self,
        session: ChatSession,
        title: str,
    ) -> ChatSession:
        session.title = title
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def update_session_last_message_at(
        self,
        session_id: uuid.UUID,
    ) -> None:
        """Update last_message_at to current time (called when a message is added)."""
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(last_message_at=datetime.now(UTC)),
        )
        await self.db.flush()

    async def delete_session(self, session: ChatSession) -> None:
        await self.db.delete(session)
        await self.db.flush()

    async def count_user_sessions(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id),
        )
        return result.scalar_one()

    # --- Messages ---

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        actions: list[dict[str, str]] | None = None,
        attached_note_ids: list[uuid.UUID] | None = None,
        token_estimate: int = 0,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            actions=actions,
            attached_note_ids=attached_note_ids,
            token_estimate=token_estimate,
        )
        self.db.add(msg)
        await self.db.flush()
        # Update session last_message_at
        await self.update_session_last_message_at(session_id)
        return msg

    async def get_messages_paginated(
        self,
        session_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChatMessage], int]:
        """Paginated message list for GET /messages endpoint (AIS 9.1)."""
        count_result = await self.db.execute(
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session_id),
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .offset(offset),
        )
        return list(result.scalars().all()), total

    async def get_recent_messages(
        self,
        session_id: uuid.UUID,
        limit: int = 25,
    ) -> list[ChatMessage]:
        """Get the most recent messages for LLM context, ordered chronologically."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit),
        )
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def get_message(
        self,
        message_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> ChatMessage | None:
        result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id, ChatMessage.session_id == session_id
            ),
        )
        return result.scalar_one_or_none()

    async def update_message_actions(
        self,
        message: ChatMessage,
        actions: list[dict[str, Any]] | None,  # type: ignore
    ) -> ChatMessage:
        await self.db.execute(
            update(ChatMessage).where(ChatMessage.id == message.id).values(actions=actions),
        )
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def update_message_content(
        self,
        message: ChatMessage,
        content: str,
    ) -> ChatMessage:
        await self.db.execute(
            update(ChatMessage).where(ChatMessage.id == message.id).values(content=content),
        )
        await self.db.flush()
        await self.db.refresh(message)
        return message

    async def find_action_by_id(
        self,
        session_id: uuid.UUID,
        action_id: str,
    ) -> tuple[ChatMessage | None, dict[str, Any] | None]:
        """Find an action (proposal or pending_confirmation) by its UUID
        across all messages in a session. Returns (message, action_dict)."""
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "assistant",
                ChatMessage.actions.is_not(None),
            )
            .order_by(ChatMessage.created_at.desc()),
        )
        messages = result.scalars().all()

        for msg in messages:
            actions = msg.actions
            if not isinstance(actions, list):
                continue
            for a in actions:
                if a.get("id") == action_id:
                    return msg, a

        return None, None

    async def has_pending_actions(self, session_id: uuid.UUID) -> bool:
        """Check whether the session has any pending proposals or
        pending_confirmations (AIS 9.2: return 409 if so).

        Uses a PostgreSQL JSONB query to scan all assistant messages
        without loading them into Python."""
        from sqlalchemy import text

        result = await self.db.execute(
            text("""
                SELECT EXISTS(
                    SELECT 1 FROM chat_messages
                    WHERE session_id = :sid
                      AND role = 'assistant'
                      AND actions IS NOT NULL
                      AND jsonb_typeof(actions) = 'array'
                      AND EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements(actions) AS elem
                          WHERE elem ->> 'status' = 'pending'
                      )
                )
            """),
            {"sid": str(session_id)},
        )
        return result.scalar_one()
