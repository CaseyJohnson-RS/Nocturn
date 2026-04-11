"""AI assistant service — Planner tool-calling loop, proposal lifecycle,
bulk operation execution.

Implements AIS spec: multi-turn Planner with function calling, proposals,
pending_confirmations, Executor one-shot for batch_transform, Redis
generating flag for concurrency control, Redis-based cancellation,
and first-token timeout.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ConflictError, NotFoundError, ValidationError
from app.common.redis import redis_client
from app.common.routerai import (
    ChatCompletionAccumulator,
    chat_completion_stream,
    get_model_context_length,
)
from app.config import settings
from app.modules.ai.locale import t
from app.modules.ai.models import ChatMessage, ChatSession
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import (
    MessageResponse,
    MessagesListResponse,
    SessionListResponse,
    SessionResponse,
)
from app.modules.ai.tools import (
    BATCH_TOOL_NAMES,
    EXECUTOR_TOOLS,
    PLANNER_TOOLS,
    ToolExecutor,
    build_summary,
    generate_deterministic_proposals,
    make_proposal,
)
from app.modules.notes.models import Note
from app.modules.notes.repository import NotesRepository
from app.modules.rag.service import RAGService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------


PLANNER_SYSTEM_PROMPT = t("planner_system_prompt")
EXECUTOR_SYSTEM_PROMPT = t("executor_system_prompt")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Approximate token count using chars-per-token ratio"""
    return int(len(text) / settings.planner_chars_per_token)


def _format_sse_event(payload: dict[str, str], event: str | None = None) -> str:
    """Format a Server-Sent Event string."""
    parts: list[str] = []
    if event:
        parts.append(f"event: {event}")
    parts.append(f"data: {json.dumps(payload, default=str)}")
    return "\n".join(parts) + "\n\n"


# ---------------------------------------------------------------------------
# region Redis

# --- Generating flag ---


def _generating_key(session_id: uuid.UUID) -> str:
    return f"generating:{session_id}"


async def _set_generating(session_id: uuid.UUID) -> bool:
    """Set the generating flag. Returns True if set (no other op running).
    TTL is a crash-safety net."""
    key = _generating_key(session_id)
    result = await redis_client.set(key, "1", nx=True, ex=120)
    return result is not None


async def _clear_generating(session_id: uuid.UUID) -> None:
    await redis_client.delete(_generating_key(session_id))


# ---------------------------------------------------------------------------
# Cancellation via Redis (cross-process safe)
#
# cancel_generation() sets a Redis key; generators poll it between
# iterations and exit early.  The generating flag is only cleared
# by the generator's finally block — never by cancel_generation().
# ---------------------------------------------------------------------------


def _cancel_key(session_id: uuid.UUID) -> str:
    return f"cancel:{session_id}"


async def _set_cancel(session_id: uuid.UUID) -> None:
    """Signal the running generator to stop. TTL is a crash-safety net."""
    await redis_client.set(_cancel_key(session_id), "1", ex=120)


async def _clear_cancel(session_id: uuid.UUID) -> None:
    await redis_client.delete(_cancel_key(session_id))


async def _is_cancelled(session_id: uuid.UUID) -> bool:
    return await redis_client.exists(_cancel_key(session_id)) == 1


# endregion
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# First-token timeout wrapper
# ---------------------------------------------------------------------------


class _LLMTimeoutError(Exception):
    """Raised when the LLM doesn't produce a first token within the limit."""


async def _stream_with_first_token_timeout(
    stream: AsyncGenerator[str, None],
    timeout_seconds: float,
) -> AsyncGenerator[str, None]:
    """Wrap an async generator to enforce a timeout on the *first* yielded
    item.  Subsequent items have no special timeout."""
    it = stream.__aiter__()
    try:
        first = await asyncio.wait_for(it.__anext__(), timeout=timeout_seconds)
    except StopAsyncIteration:
        return
    except TimeoutError:
        raise _LLMTimeoutError(t("llm_timeout", timeout=timeout_seconds))

    yield first

    # Remaining items — no special timeout
    try:
        while True:
            yield await it.__anext__()
    except StopAsyncIteration:
        pass


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------


async def _token_budget() -> int:
    """Calculate the available token budget for history"""
    model_window = settings.routerai_llm_context_window
    if settings.routerai_fetch_model_context_window and settings.routerai_llm_model:
        fetched = await get_model_context_length(settings.routerai_llm_model)
        if fetched is not None:
            model_window = fetched
    return max(
        model_window - settings.system_prompt_tokens - settings.safety_margin_tokens,
        0,
    )


# ---------------------------------------------------------------------------
# Actions summary for LLM context
# ---------------------------------------------------------------------------


def _actions_summary_for_context(actions: list[dict[str, Any]] | None) -> str:
    """Build a short text summary of actions for LLM context.
    Full snapshots (data) are never passed into context."""
    if not actions:
        return ""
    parts: list[str] = []
    for a in actions:
        if not isinstance(a, dict):  # type: ignore - Let's doublecheck this
            continue
        atype = a.get("type", "")
        if atype == "proposal":
            ptype = a.get("proposal_type", "")
            status = a.get("status", "pending")
            summary = a.get("summary") or ""
            if summary:
                parts.append(
                    t(
                        "context_proposal_with_summary",
                        ptype=ptype,
                        status=status,
                        summary=summary,
                    )
                )
            else:
                note_id = a.get("note_id", "")
                parts.append(
                    t(
                        "context_proposal_no_summary",
                        ptype=ptype,
                        note_id=note_id,
                        status=status,
                    )
                )
        elif atype == "pending_confirmation":
            op = a.get("operation_type", "")
            status = a.get("status", "pending")
            n = len(a.get("note_ids", []))
            parts.append(t("context_confirmation", op=op, n=n, status=status))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# region AIService


class AIService:
    def __init__(self, db: AsyncSession):
        self.repo = AIRepository(db)
        self.notes_repo = NotesRepository(db)
        self.rag = RAGService(db)
        self.db = db

    # -----------------------------------------------------------------------
    # Session management
    # -----------------------------------------------------------------------

    async def create_session(
        self,
        user_id: uuid.UUID,
        dismiss_session_id: uuid.UUID | None = None,
    ) -> SessionResponse:
        if dismiss_session_id:
            await self._dismiss_all_pending(user_id, dismiss_session_id)

        count = await self.repo.count_user_sessions(user_id)
        if count >= settings.max_chat_sessions_per_user:
            raise ConflictError("Chat session limit reached")

        session = await self.repo.create_session(user_id)
        return SessionResponse.model_validate(session)

    async def list_sessions(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> SessionListResponse:
        sessions, total = await self.repo.list_sessions(user_id, limit, offset)
        return SessionListResponse(
            items=[SessionResponse.model_validate(s) for s in sessions],
            total=total,
        )

    async def get_messages(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> MessagesListResponse:
        """Paginated message history"""
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")
        messages, total = await self.repo.get_messages_paginated(
            session_id,
            limit,
            offset,
        )
        return MessagesListResponse(
            items=[MessageResponse.model_validate(m) for m in messages],
            total=total,
        )

    async def update_session(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        title: str,
    ) -> SessionResponse:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")
        session = await self.repo.update_session_title(session, title)
        return SessionResponse.model_validate(session)

    async def delete_session(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")
        await self.repo.delete_session(session)

    # -----------------------------------------------------------------------
    # Send message — multi-turn Planner tool-calling loop
    # -----------------------------------------------------------------------

    async def pre_validate_send(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        content: str,
    ) -> tuple[int, str] | None:
        """Validate preconditions before starting the SSE stream.
        Returns (status_code, detail) on error, or None on success.
        """
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            return (404, "Chat session not found")
        if len(content) > settings.max_message_length:
            return (400, "Message too long")
        if await self.repo.has_pending_actions(session_id):
            return (409, "Session has unprocessed proposals or pending confirmations")
        return None

    async def send_message(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        content: str,
        attached_note_ids: list[uuid.UUID] | None = None,
    ) -> AsyncGenerator[str]:
        """Stream LLM response as SSE events"""
        # Acquire generating lock (NX guarantees only one wins)
        if not await _set_generating(session_id):
            yield _format_sse_event(
                {"code": "conflict", "message": "Assistant is already generating"},
                event="ai:error",
            )
            yield _format_sse_event({}, event="ai:done")
            return

        try:
            session = await self.repo.get_session(session_id, user_id)
            if not session:
                yield _format_sse_event(
                    {"code": "not_found", "message": "Session not found"},
                    event="ai:error",
                )
                yield _format_sse_event({}, event="ai:done")
                return

            async for event in self._run_planner(
                user_id,
                session_id,
                session,
                content,
                attached_note_ids,
            ):
                yield event
        finally:
            await _clear_cancel(session_id)
            await _clear_generating(session_id)

    async def _run_planner(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        session: ChatSession,
        content: str,
        attached_note_ids: list[uuid.UUID] | None,
    ) -> AsyncGenerator[str]:
        """Inner generator: Planner multi-turn tool loop."""
        note_ids = attached_note_ids or []

        # 1. Save user message
        await self.repo.add_message(
            session_id=session_id,
            role="user",
            content=content,
            attached_note_ids=note_ids or None,
            token_estimate=_estimate_tokens(content),
        )

        # 2. Build LLM messages with history
        llm_messages = await self._build_llm_messages(
            session_id,
            user_id,
            note_ids,
        )

        # 3. Multi-turn tool-calling loop
        actions: list[dict[str, Any]] = []
        tool_executor = ToolExecutor(self.db, user_id, actions)
        full_content_parts: list[str] = []
        max_tool_rounds = 10
        first_llm_call = True

        try:
            for _round in range(max_tool_rounds):
                # Check cancellation between rounds (Redis-based, cross-process)
                if await _is_cancelled(session_id):
                    break

                accumulator = ChatCompletionAccumulator()

                raw_stream = chat_completion_stream(
                    llm_messages,
                    tools=PLANNER_TOOLS,
                    accumulator=accumulator,
                )

                # First-token timeout on the first LLM call
                if first_llm_call:
                    stream = _stream_with_first_token_timeout(
                        raw_stream,
                        timeout_seconds=settings.llm_first_token_timeout_seconds,
                    )
                    first_llm_call = False
                else:
                    stream = raw_stream

                async for delta in stream:
                    full_content_parts.append(delta)
                    yield _format_sse_event(
                        {"delta": delta},
                        event="ai:text_delta",
                    )

                # If no tool calls, we're done
                if not accumulator.has_tool_calls:
                    break

                # Build the assistant message with tool_calls for context
                assistant_turn: dict[str, Any] = {"role": "assistant"}
                if accumulator.full_content:
                    assistant_turn["content"] = accumulator.full_content
                assistant_turn["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in accumulator.tool_calls
                ]
                llm_messages.append(assistant_turn)

                # Execute each tool call
                for tc in accumulator.tool_calls:
                    if await _is_cancelled(session_id):
                        break

                    result_str = await tool_executor.execute(
                        tc.name,
                        tc.arguments,
                    )
                    llm_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_str,
                        }
                    )

                    # Emit proposal/confirmation SSE events
                    for action in actions:
                        if action.get("_emitted"):
                            continue
                        action["_emitted"] = True
                        clean = {k: v for k, v in action.items() if k != "_emitted"}
                        if action["type"] == "proposal":
                            yield _format_sse_event(
                                clean,
                                event="ai:proposal",
                            )
                        elif action["type"] == "pending_confirmation":
                            yield _format_sse_event(
                                clean,
                                event="ai:pending_confirmation",
                            )

                # If only batch tools were called, break
                tool_names = {tc.name for tc in accumulator.tool_calls}
                if tool_names <= BATCH_TOOL_NAMES:
                    break

        except _LLMTimeoutError as exc:
            logger.warning("LLM timeout for session %s: %s", session_id, exc)
            yield _format_sse_event(
                {"code": "llm_timeout", "message": str(exc)},
                event="ai:error",
            )
            yield _format_sse_event({}, event="ai:done")
            return

        except Exception as exc:
            logger.exception("Planner failed for session %s", session_id)
            yield _format_sse_event(
                {"code": "llm_unavailable", "message": str(exc)},
                event="ai:error",
            )
            # Save partial response if any
            response_text = "".join(full_content_parts)
            if response_text:
                clean_actions = self._clean_actions(actions)
                await self.repo.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_text,
                    actions=clean_actions or None,
                    token_estimate=_estimate_tokens(response_text),
                )
            yield _format_sse_event({}, event="ai:done")
            return

        # 4. Save assistant message
        response_text = "".join(full_content_parts)
        clean_actions = self._clean_actions(actions)

        await self.repo.add_message(
            session_id=session_id,
            role="assistant",
            content=response_text or "(No text response)",
            actions=clean_actions or None,
            token_estimate=_estimate_tokens(response_text),
        )

        # 5. Auto-title from first user message
        if session.title is None and content:
            title = content[:100].strip()
            await self.repo.update_session_title(session, title)

        # 6. Done
        yield _format_sse_event({}, event="ai:done")

    # -----------------------------------------------------------------------
    # Cancel active generation
    # -----------------------------------------------------------------------

    async def cancel_generation(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> dict[str, str]:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")

        # Check that there is an active generation to cancel
        key = _generating_key(session_id)
        if not await redis_client.exists(key):
            raise ConflictError("No active operation to cancel")

        # Signal the running generator to stop via Redis (cross-process).
        # The generator's finally block clears both cancel and generating keys.
        await _set_cancel(session_id)
        return {"status": "cancelled"}

    # -----------------------------------------------------------------------
    # Proposal lifecycle
    # -----------------------------------------------------------------------

    async def update_action_status(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        message_id: uuid.UUID,
        action_id: str,
        new_status: str,
    ) -> MessageResponse:
        """Apply or dismiss a single proposal"""
        if new_status not in ("applied", "dismissed"):
            raise ValidationError("Status must be 'applied' or 'dismissed'")

        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")

        msg = await self.repo.get_message(message_id, session_id)
        if not msg or msg.role != "assistant":
            raise NotFoundError("Assistant message not found")

        actions: list[dict[str, Any]] | None = msg.actions
        if not actions:
            raise ValidationError("No actions on this message")

        target = None
        for a in actions:
            if a.get("id") == action_id and a.get("type") == "proposal":
                target = a
                break

        if target is None:
            raise NotFoundError("Proposal not found")
        if target.get("status") != "pending":
            raise ConflictError("Proposal already finalized")

        target["summary"] = build_summary(target, new_status)
        target["status"] = new_status
        target["data"] = None

        msg = await self.repo.update_message_actions(msg, actions)
        return MessageResponse.model_validate(msg)

    # -----------------------------------------------------------------------
    # Bulk confirmation
    # -----------------------------------------------------------------------

    async def pre_validate_confirm(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        confirmation_id: str,
    ) -> tuple[int, str] | None:
        """Validate preconditions before starting the confirm SSE stream.
        Bug 1 fix: errors are returned as (status, detail) tuples so the
        router can send a proper JSON error *before* SSE headers."""
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            return (404, "Chat session not found")

        msg, confirmation = await self.repo.find_action_by_id(
            session_id,
            confirmation_id,
        )
        if not msg or not confirmation or confirmation.get("type") != "pending_confirmation":
            return (404, "Confirmation not found")
        if confirmation.get("status") != "pending":
            return (409, "Confirmation already processed")
        return None

    async def confirm_bulk(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        confirmation_id: str,
    ) -> AsyncGenerator[str]:
        """Confirm a pending_confirmation and stream generated proposals.

        Bug 1 + 5 fix: generating flag is set inside the generator;
        pre_validate_confirm() must be called by the router before this.
        """
        if not await _set_generating(session_id):
            yield _format_sse_event(
                {"code": "conflict", "message": "Another operation is in progress"},
                event="ai:error",
            )
            yield _format_sse_event({}, event="ai:done")
            return

        try:
            async for event in self._execute_bulk(
                user_id,
                session_id,
                confirmation_id,
            ):
                yield event
        finally:
            await _clear_cancel(session_id)
            await _clear_generating(session_id)

    async def _execute_bulk(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        confirmation_id: str,
    ) -> AsyncGenerator[str]:
        """Execute a confirmed bulk operation, yielding SSE events"""
        msg, confirmation = await self.repo.find_action_by_id(
            session_id,
            confirmation_id,
        )
        if not msg or not confirmation:
            yield _format_sse_event(
                {"code": "not_found", "message": "Confirmation not found"},
                event="ai:error",
            )
            yield _format_sse_event({}, event="ai:done")
            return

        # Mark as confirmed
        confirmation["status"] = "confirmed"
        await self.repo.update_message_actions(msg, msg.actions)

        op_type = confirmation.get("operation_type", "")
        note_ids = confirmation.get("note_ids", [])
        params = confirmation.get("params", {})

        proposals: list[dict[str, Any]] = []

        try:
            if op_type == "transform":
                async for proposal in self._run_executor_batch(
                    user_id,
                    session_id,
                    note_ids,
                    params.get("instruction", ""),
                ):
                    proposals.append(proposal)
                    yield _format_sse_event(proposal, event="ai:proposal")
            else:
                proposals = await generate_deterministic_proposals(
                    self.db,
                    user_id,
                    confirmation,
                )
                for p in proposals:
                    if await _is_cancelled(session_id):
                        break
                    yield _format_sse_event(p, event="ai:proposal")

        except Exception as exc:
            logger.exception("Bulk operation failed for session %s", session_id)
            if not proposals:
                yield _format_sse_event(
                    {"code": "bulk_failed", "message": str(exc)},
                    event="ai:error",
                )

        # Save proposals as a new assistant message
        if proposals:
            await self.repo.add_message(
                session_id=session_id,
                role="assistant",
                content=t("bulk_proposals_generated", count=len(proposals), op=op_type),
                actions=proposals,
                token_estimate=_estimate_tokens(str(proposals)),
            )

        # Update confirmation summary
        n = len(note_ids)
        confirmation["summary"] = t(
            "bulk_confirmed_with_proposals",
            op=op_type,
            n=n,
            proposals_count=len(proposals),
        )
        await self.repo.update_message_actions(msg, msg.actions)

        yield _format_sse_event({}, event="ai:done")

    async def _run_executor_batch(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        note_ids: list[str],
        instruction: str,
    ) -> AsyncGenerator[dict[str, Any]]:
        """Call Executor (one-shot LLM) for each note in batch_transform.
        Checks Redis cancel key between notes (cross-process safe)."""
        for raw_id in note_ids:
            if await _is_cancelled(session_id):
                break

            try:
                nid = uuid.UUID(raw_id)
            except ValueError:
                continue

            note = await self.notes_repo.get_active_note(nid, user_id)
            if not note:
                continue

            try:
                proposals = await self._execute_single_note(note, instruction)
                for p in proposals:
                    yield p
            except Exception as exc:
                logger.warning("Executor failed for note %s: %s", nid, exc)
                continue

    async def _execute_single_note(
        self,
        note: Note,
        instruction: str,
    ) -> list[dict[str, Any]]:
        """One-shot Executor call for a single note"""
        system_prompt = EXECUTOR_SYSTEM_PROMPT.format(
            instruction=instruction,
            title=note.title or "Untitled",
            tags=", ".join(t.name for t in note.tags) if note.tags else "none",
            content=note.content or "",
        )

        messages = [{"role": "system", "content": system_prompt}]

        accumulator = ChatCompletionAccumulator()
        async for _ in chat_completion_stream(
            messages,
            model=settings.routerai_executor_model or None,
            tools=EXECUTOR_TOOLS,
            accumulator=accumulator,
        ):
            pass

        proposals: list[dict[str, Any]] = []
        for tc in accumulator.tool_calls:
            try:
                args: dict[str, Any] = json.loads(tc.arguments) if tc.arguments else {}
            except json.JSONDecodeError:
                continue

            if tc.name == "edit_note":
                title = args.get("title")
                content = args.get("content")
                if title or content:
                    proposals.append(
                        make_proposal(
                            "edit_note",
                            str(note.id),
                            {"title": title, "content": content},
                        )
                    )
            elif tc.name == "add_tags":
                tags = args.get("tags", [])
                if tags:
                    proposals.append(
                        make_proposal(
                            "add_tags",
                            str(note.id),
                            {"tags": tags},
                        )
                    )
            elif tc.name == "remove_tags":
                tags = args.get("tags", [])
                if tags:
                    proposals.append(
                        make_proposal(
                            "remove_tags",
                            str(note.id),
                            {"tags": tags},
                        )
                    )
            elif tc.name == "delete_note":
                proposals.append(
                    make_proposal(
                        "delete_note",
                        str(note.id),
                        {"note_title": note.title or "Untitled"},
                    )
                )

        return proposals

    # -----------------------------------------------------------------------
    # Dismiss bulk
    # -----------------------------------------------------------------------

    async def dismiss_bulk(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        confirmation_id: str,
    ) -> MessageResponse:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")

        msg, confirmation = await self.repo.find_action_by_id(
            session_id,
            confirmation_id,
        )
        if not msg or not confirmation:
            raise NotFoundError("Confirmation not found")
        if confirmation.get("type") != "pending_confirmation":
            raise NotFoundError("Confirmation not found")
        if confirmation.get("status") != "pending":
            raise ConflictError("Confirmation already processed")

        confirmation["status"] = "dismissed"
        confirmation["summary"] = build_summary(confirmation, "dismissed")
        msg = await self.repo.update_message_actions(msg, msg.actions)
        return MessageResponse.model_validate(msg)

    # -----------------------------------------------------------------------
    # Dismiss all pending in a session
    # -----------------------------------------------------------------------

    async def _dismiss_all_pending(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            return

        messages = await self.repo.get_recent_messages(session_id, limit=100)
        for msg in messages:
            if not msg.actions or msg.role != "assistant":
                continue
            actions = msg.actions
            changed = False
            for a in actions:
                if a.get("status") != "pending":
                    continue
                a["status"] = "dismissed"
                a["summary"] = build_summary(a, "dismissed")
                if a.get("type") == "proposal":
                    a["data"] = None
                changed = True
            if changed:
                await self.repo.update_message_actions(msg, actions)

    # -----------------------------------------------------------------------
    # Build LLM messages
    # -----------------------------------------------------------------------

    async def _build_llm_messages(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        note_ids: list[uuid.UUID],
    ) -> list[dict[str, str]]:
        system_content = PLANNER_SYSTEM_PROMPT.format(
            current_date=datetime.now(UTC).strftime("%Y-%m-%d"),
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

        history = await self.repo.get_recent_messages(
            session_id,
            limit=settings.max_messages_in_context,
        )

        system_tokens = _estimate_tokens(system_content)
        budget = await _token_budget() - system_tokens
        selected: list[ChatMessage] = []
        used = 0

        for msg in reversed(history):
            if used + msg.token_estimate > budget:
                break
            selected.append(msg)
            used += msg.token_estimate
        selected.reverse()

        # Edge case
        if not selected and history:
            selected = [history[-1]]

        for i, msg in enumerate(selected):
            msg_content = msg.content
            is_last_user = msg.role == "user" and i == len(selected) - 1

            if is_last_user and note_ids:
                previews = await self._build_attached_previews(user_id, note_ids)
                if previews:
                    msg_content += "\n\n" + t("attached_notes_header") + "\n" + previews

            if msg.role == "assistant" and msg.actions:
                summary = _actions_summary_for_context(msg.actions)
                if summary:
                    msg_content += "\n\n" + summary

            messages.append({"role": msg.role, "content": msg_content})

        return messages

    async def _build_attached_previews(
        self,
        user_id: uuid.UUID,
        note_ids: list[uuid.UUID],
    ) -> str:
        notes = await self.notes_repo.get_notes_by_ids(note_ids, user_id)
        lines: list[str] = []
        for n in notes[: settings.max_attached_notes]:
            if n.deleted_at is not None:
                continue
            preview = (n.content or "")[:100]
            lines.append(f"- {n.id} | {n.title or 'Untitled'}: {preview}")
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _clean_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        if not actions:
            return None
        return [{k: v for k, v in a.items() if k != "_emitted"} for a in actions]

# endregion
# ---------------------------------------------------------------------------
