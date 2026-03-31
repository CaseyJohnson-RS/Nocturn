import json
import logging
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ConflictError, NotFoundError, ValidationError
from app.common.routerai import chat_completion_stream
from app.config import settings
from app.modules.ai.models import ChatMessage
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import (
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    MessageResponse,
)
from app.modules.notes.repository import NotesRepository
from app.modules.rag.service import RAGService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Nocturn AI, a helpful assistant embedded in a note-taking app. "
    "Answer the user's question using the provided note excerpts as context. "
    "If the notes don't contain relevant information, say so honestly. "
    "Be concise and reference specific notes when possible."
)


def _estimate_tokens(text: str) -> int:
    return int(len(text) / settings.planner_chars_per_token)


def _build_context_block(notes_content: list[dict]) -> str:
    """Format retrieved note chunks into a context block for the system prompt."""
    if not notes_content:
        return ""
    parts = []
    for i, note in enumerate(notes_content, 1):
        parts.append(f"[Source {i}: {note['title'] or 'Untitled'}]\n{note['content']}")
    return "\n\n---\n\n".join(parts)


class AIService:
    def __init__(self, db: AsyncSession):
        self.repo = AIRepository(db)
        self.notes_repo = NotesRepository(db)
        self.rag = RAGService(db)
        self.db = db

    # --- Session management ---

    async def create_session(
        self, user_id: uuid.UUID, title: str | None = None,
    ) -> SessionResponse:
        count = await self.repo.count_user_sessions(user_id)
        if count >= settings.max_chat_sessions_per_user:
            raise ConflictError("Chat session limit reached")

        session = await self.repo.create_session(user_id, title)
        return SessionResponse.model_validate(session)

    async def get_session(
        self, user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> SessionDetailResponse:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")
        return SessionDetailResponse.model_validate(session)

    async def list_sessions(
        self, user_id: uuid.UUID, limit: int = 50, offset: int = 0,
    ) -> SessionListResponse:
        sessions, total = await self.repo.list_sessions(user_id, limit, offset)
        return SessionListResponse(
            items=[SessionResponse.model_validate(s) for s in sessions],
            total=total,
        )

    async def update_session(
        self, user_id: uuid.UUID, session_id: uuid.UUID, title: str,
    ) -> SessionResponse:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")
        session = await self.repo.update_session_title(session, title)
        return SessionResponse.model_validate(session)

    async def delete_session(
        self, user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")
        await self.repo.delete_session(session)

    # --- Chat ---

    async def send_message(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        content: str,
        note_ids: list[uuid.UUID] | None = None,
    ) -> AsyncGenerator[str]:
        """Process user message: save it, gather context, stream LLM reply.

        Yields SSE-formatted chunks. The final chunk contains the saved
        assistant message metadata as JSON.
        """
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")

        if len(content) > settings.max_message_length:
            raise ValidationError("Message too long")

        # 1. Save user message
        user_msg = await self.repo.add_message(
            session_id=session_id,
            role="user",
            content=content,
            token_estimate=_estimate_tokens(content),
        )

        # 2. Gather context from RAG + explicitly attached notes
        context_notes = await self._gather_context(user_id, content, note_ids or [])
        source_ids = [str(n["note_id"]) for n in context_notes]

        # 3. Build messages for LLM
        llm_messages = await self._build_llm_messages(session_id, context_notes)

        # 4. Stream LLM response
        full_response = []
        async for delta in chat_completion_stream(llm_messages):
            full_response.append(delta)
            yield f"data: {json.dumps({'delta': delta})}\n\n"

        response_text = "".join(full_response)

        # 5. Save assistant message
        assistant_msg = await self.repo.add_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            sources=json.dumps(source_ids) if source_ids else None,
            token_estimate=_estimate_tokens(response_text),
        )

        # 6. Auto-title the session if it's the first exchange
        if session.title is None:
            title = content[:100].strip()
            await self.repo.update_session_title(session, title)

        # 7. Yield final metadata event
        msg_data = MessageResponse.model_validate(assistant_msg).model_dump(mode="json")
        yield f"data: {json.dumps({'done': True, 'message': msg_data})}\n\n"

    async def _gather_context(
        self,
        user_id: uuid.UUID,
        query: str,
        explicit_note_ids: list[uuid.UUID],
    ) -> list[dict]:
        """Combine RAG search results with explicitly attached notes."""
        context: list[dict] = []
        seen_note_ids: set[uuid.UUID] = set()

        # Explicitly attached notes first
        if explicit_note_ids:
            notes = await self.notes_repo.get_notes_by_ids(explicit_note_ids, user_id)
            for note in notes[: settings.max_attached_notes]:
                if note.id not in seen_note_ids:
                    context.append({
                        "note_id": note.id,
                        "title": note.title,
                        "content": (note.content or "")[:2000],
                    })
                    seen_note_ids.add(note.id)

        # RAG search for additional context
        remaining = settings.max_sources_per_response - len(context)
        if remaining > 0:
            search_results = await self.rag.search(user_id, query, limit=remaining)
            for result in search_results.results:
                if result.note_id not in seen_note_ids:
                    # Fetch note title for context block
                    note = await self.notes_repo.get_note_by_id(result.note_id, user_id)
                    if note:
                        context.append({
                            "note_id": result.note_id,
                            "title": note.title,
                            "content": result.content,
                        })
                        seen_note_ids.add(result.note_id)

        return context

    async def _build_llm_messages(
        self,
        session_id: uuid.UUID,
        context_notes: list[dict],
    ) -> list[dict]:
        """Build the message list for the LLM, respecting token budget."""
        # System prompt with context
        context_block = _build_context_block(context_notes)
        system_content = SYSTEM_PROMPT
        if context_block:
            system_content += f"\n\n## Relevant notes:\n\n{context_block}"

        messages: list[dict] = [{"role": "system", "content": system_content}]

        # Add recent conversation history
        history = await self.repo.get_recent_messages(
            session_id, limit=settings.max_messages_in_context,
        )

        # Trim history to fit token budget
        # Budget = model context - system_prompt - safety_margin
        system_tokens = _estimate_tokens(system_content)
        budget = _token_budget() - system_tokens
        selected: list[ChatMessage] = []
        used = 0
        for msg in reversed(history):
            if used + msg.token_estimate > budget:
                break
            selected.append(msg)
            used += msg.token_estimate
        selected.reverse()

        for msg in selected:
            messages.append({"role": msg.role, "content": msg.content})

        return messages


def _token_budget() -> int:
    """Rough token budget for conversation history.

    # TODO: replace with actual model context window size from RouterAI config.
    # For now assume 8k context window — subtract system prompt and safety margin.
    """
    return 8000 - settings.system_prompt_tokens - settings.safety_margin_tokens
