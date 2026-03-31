"""AI assistant service — Planner tool-calling loop, proposal lifecycle,
bulk operation execution.

Implements AIS spec: multi-turn Planner with function calling, proposals,
pending_confirmations, Executor one-shot for batch_transform, and Redis
generating flag for concurrency control.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ConflictError, NotFoundError, ValidationError
from app.common.redis import redis_client
from app.common.routerai import (
    ChatCompletionAccumulator,
    chat_completion_stream,
    get_model_context_length,
)
from app.config import settings
from app.modules.ai.models import ChatMessage
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import (
    MessageResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from app.modules.ai.tools import (
    BATCH_TOOL_NAMES,
    EXECUTOR_TOOLS,
    PLANNER_TOOLS,
    PROPOSE_TOOL_NAMES,
    READ_TOOL_NAMES,
    ToolExecutor,
    _build_summary,
    generate_deterministic_proposals,
    make_proposal,
)
from app.modules.notes.repository import NotesRepository
from app.modules.rag.service import RAGService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts (AIS 8.1 & 8.2)
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """\
You are Nocturn AI, an assistant embedded in a note-taking app.
You help the user find, analyse and modify their notes.

## Rules

1. Read notes via tools search_notes, get_note, list_tags.
2. For changes use propose_* (single) or batch_* (bulk).
   You cannot modify notes directly — only propose changes.
3. The user decides whether to apply proposals.
4. No more than one proposal of each type per note per response.
5. No more than one batch_* operation per response. If the request requires
   several — execute the first, suggest the user repeat for the next.
6. Maximum notes in one batch_* operation — 25.
   If more are needed — process the first 25, suggest repeating.
7. Reply in the user's language.
8. If no notes are found — say so. Do not invent content.
9. Reference notes in text as [[note:uuid|Title]].
   Maximum 5 references per response (not counting user-attached notes).
10. Use get_note only when full content is needed (editing, detailed analysis).
    For general answers content_preview from search_notes is enough.
11. For batch_replace regex uses RE2 — do not use lookahead, lookbehind,
    or backreferences.

## Context

Current date: {current_date}
Attached notes are shown in the user's last message.
If you need full content of an attached note, use get_note.\
"""

EXECUTOR_SYSTEM_PROMPT = """\
Process the note according to the instruction. Use tools to make changes.
If the instruction does not apply to this note — do not call any tools.

## Instruction
{instruction}

## Note
Title: {title}
Tags: {tags}
Content:
{content}\
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    return int(len(text) / settings.planner_chars_per_token)


def _format_sse_event(payload: dict, event: str | None = None) -> str:
    parts = []
    if event:
        parts.append(f"event: {event}")
    parts.append(f"data: {json.dumps(payload, default=str)}")
    return "\n".join(parts) + "\n\n"


def _generating_key(session_id: uuid.UUID) -> str:
    return f"generating:{session_id}"


async def _set_generating(session_id: uuid.UUID) -> bool:
    """Set the generating flag. Returns True if set (no other op running)."""
    key = _generating_key(session_id)
    # SET NX with a 120s TTL as crash-safety net
    result = await redis_client.set(key, "1", nx=True, ex=120)
    return result is not None


async def _clear_generating(session_id: uuid.UUID) -> None:
    await redis_client.delete(_generating_key(session_id))


async def _token_budget() -> int:
    model_window = settings.routerai_llm_context_window
    if settings.routerai_fetch_model_context_window and settings.routerai_llm_model:
        fetched = await get_model_context_length(settings.routerai_llm_model)
        if fetched is not None:
            model_window = fetched
    return max(
        model_window - settings.system_prompt_tokens - settings.safety_margin_tokens,
        0,
    )


def _actions_summary_for_context(actions: list | dict | None) -> str:
    """Build a short text summary of actions for LLM context (AIS 7.4)."""
    if not actions:
        return ""
    if isinstance(actions, dict):
        actions = [actions]
    parts = []
    for a in actions:
        atype = a.get("type", "")
        if atype == "proposal":
            ptype = a.get("proposal_type", "")
            status = a.get("status", "pending")
            note_id = a.get("note_id", "")
            summary = a.get("summary") or ""
            if summary:
                parts.append(f"[{ptype} — {status}: {summary}]")
            else:
                parts.append(f"[{ptype} for note {note_id} — {status}]")
        elif atype == "pending_confirmation":
            op = a.get("operation_type", "")
            status = a.get("status", "pending")
            n = len(a.get("note_ids", []))
            parts.append(f"[{op} for {n} notes — {status}]")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# AIService
# ---------------------------------------------------------------------------

class AIService:
    def __init__(self, db: AsyncSession):
        self.repo = AIRepository(db)
        self.notes_repo = NotesRepository(db)
        self.rag = RAGService(db)
        self.db = db

    # -----------------------------------------------------------------------
    # Session management (unchanged from before)
    # -----------------------------------------------------------------------

    async def create_session(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
        dismiss_session_id: uuid.UUID | None = None,
    ) -> SessionResponse:
        # Dismiss pending proposals in old session if requested (AIS 10.2)
        if dismiss_session_id:
            await self._dismiss_all_pending(user_id, dismiss_session_id)

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
        Returns (status_code, detail) tuple on error, or None on success."""
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            return (404, "Chat session not found")
        if len(content) > settings.max_message_length:
            return (400, "Message too long")
        if not await _set_generating(session_id):
            return (409, "Assistant is already generating a response")
        return None

    async def send_message(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        content: str,
        note_ids: list[uuid.UUID] | None = None,
    ) -> AsyncGenerator[str]:
        """Stream LLM response. Call pre_validate_send() before starting."""
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            return

        try:
            async for event in self._run_planner(
                user_id, session_id, session, content, note_ids,
            ):
                yield event
        finally:
            await _clear_generating(session_id)

    async def _run_planner(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        session,
        content: str,
        note_ids: list[uuid.UUID] | None,
    ) -> AsyncGenerator[str]:
        """Inner generator for the Planner multi-turn tool loop."""
        # 1. Save user message
        user_msg = await self.repo.add_message(
            session_id=session_id,
            role="user",
            content=content,
            attached_note_ids=note_ids or None,
            token_estimate=_estimate_tokens(content),
        )

        # 2. Build LLM messages with history
        llm_messages = await self._build_llm_messages(
            session_id, user_id, note_ids or [],
        )

        # 3. Multi-turn tool-calling loop
        actions: list[dict] = []
        tool_executor = ToolExecutor(self.db, user_id, actions)
        full_content_parts: list[str] = []
        max_tool_rounds = 10  # safety limit

        try:
            for _round in range(max_tool_rounds):
                accumulator = ChatCompletionAccumulator()

                async for delta in chat_completion_stream(
                    llm_messages,
                    tools=PLANNER_TOOLS,
                    accumulator=accumulator,
                ):
                    full_content_parts.append(delta)
                    yield _format_sse_event({"delta": delta}, event="ai:text_delta")

                # If no tool calls, we're done
                if not accumulator.has_tool_calls:
                    break

                # Build the assistant message with tool_calls for context
                assistant_turn: dict = {"role": "assistant"}
                if accumulator.full_content:
                    assistant_turn["content"] = accumulator.full_content
                assistant_turn["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in accumulator.tool_calls
                ]
                llm_messages.append(assistant_turn)

                # Execute each tool call
                for tc in accumulator.tool_calls:
                    result_str = await tool_executor.execute(tc.name, tc.arguments)
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })

                    # Emit proposal/confirmation SSE events as they're registered
                    for action in actions:
                        if action.get("_emitted"):
                            continue
                        action["_emitted"] = True
                        if action["type"] == "proposal":
                            yield _format_sse_event(
                                {k: v for k, v in action.items() if k != "_emitted"},
                                event="ai:proposal",
                            )
                        elif action["type"] == "pending_confirmation":
                            yield _format_sse_event(
                                {k: v for k, v in action.items() if k != "_emitted"},
                                event="ai:pending_confirmation",
                            )

                # If only batch tools were called (no more text expected), break
                tool_names = {tc.name for tc in accumulator.tool_calls}
                if tool_names <= BATCH_TOOL_NAMES:
                    break

        except Exception as exc:
            logger.exception("Planner failed for session %s", session_id)
            yield _format_sse_event(
                {"code": "llm_unavailable", "message": str(exc)},
                event="ai:error",
            )
            # Save partial response if we have any
            response_text = "".join(full_content_parts)
            if response_text:
                await self.repo.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_text,
                    token_estimate=_estimate_tokens(response_text),
                )
            yield _format_sse_event({}, event="ai:done")
            return

        # 4. Save assistant message
        response_text = "".join(full_content_parts)
        # Clean _emitted flags from actions before saving
        clean_actions = [
            {k: v for k, v in a.items() if k != "_emitted"}
            for a in actions
        ] if actions else None

        assistant_msg = await self.repo.add_message(
            session_id=session_id,
            role="assistant",
            content=response_text or "(No text response)",
            actions=clean_actions,
            token_estimate=_estimate_tokens(response_text),
        )

        # 5. Auto-title
        if session.title is None and content:
            title = content[:100].strip()
            await self.repo.update_session_title(session, title)

        # 6. Done
        msg_data = MessageResponse.model_validate(assistant_msg).model_dump(mode="json")
        yield _format_sse_event({"message": msg_data}, event="ai:done")

    # -----------------------------------------------------------------------
    # Cancel active generation (AIS 9.3)
    # -----------------------------------------------------------------------

    async def cancel_generation(
        self, user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> dict:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")

        key = _generating_key(session_id)
        deleted = await redis_client.delete(key)
        if not deleted:
            raise ConflictError("No active operation to cancel")
        return {"status": "cancelled"}

    # -----------------------------------------------------------------------
    # Proposal lifecycle (AIS 5.2 / 5.3)
    # -----------------------------------------------------------------------

    async def update_action_status(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        message_id: uuid.UUID,
        action_id: str,
        new_status: str,
    ) -> MessageResponse:
        """Apply or dismiss a single proposal (PATCH endpoint)."""
        if new_status not in ("applied", "dismissed"):
            raise ValidationError("Status must be 'applied' or 'dismissed'")

        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")

        msg = await self.repo.get_message(message_id, session_id)
        if not msg or msg.role != "assistant":
            raise NotFoundError("Assistant message not found")

        actions = msg.actions
        if not actions:
            raise ValidationError("No actions on this message")
        if isinstance(actions, dict):
            actions = [actions]

        target = None
        for a in actions:
            if a.get("id") == action_id and a.get("type") == "proposal":
                target = a
                break

        if target is None:
            raise NotFoundError("Proposal not found")

        if target.get("status") != "pending":
            raise ConflictError("Proposal already finalized")

        # Build summary, clear data, update status
        target["summary"] = _build_summary(target, new_status)
        target["status"] = new_status
        target["data"] = None

        msg = await self.repo.update_message_actions(msg, actions)
        return MessageResponse.model_validate(msg)

    # -----------------------------------------------------------------------
    # Bulk confirmation (AIS 6.2)
    # -----------------------------------------------------------------------

    async def confirm_bulk(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        confirmation_id: str,
    ) -> AsyncGenerator[str]:
        """Confirm a pending_confirmation and generate proposals."""
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            raise NotFoundError("Chat session not found")

        if not await _set_generating(session_id):
            raise ConflictError("Another operation is in progress")

        try:
            async for event in self._execute_bulk(
                user_id, session_id, confirmation_id,
            ):
                yield event
        finally:
            await _clear_generating(session_id)

    async def _execute_bulk(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        confirmation_id: str,
    ) -> AsyncGenerator[str]:
        """Execute a confirmed bulk operation, yielding SSE events."""
        # Find the message containing this confirmation
        msg, confirmation = await self.repo.find_action_by_id(
            session_id, confirmation_id,
        )
        if not msg or not confirmation:
            raise NotFoundError("Confirmation not found")
        if confirmation.get("status") != "pending":
            raise ConflictError("Confirmation already processed")

        # Mark as confirmed
        confirmation["status"] = "confirmed"
        await self.repo.update_message_actions(msg, msg.actions)

        op_type = confirmation.get("operation_type", "")
        note_ids = confirmation.get("note_ids", [])
        params = confirmation.get("params", {})

        # Create a new assistant message for the generated proposals
        proposals: list[dict] = []

        try:
            if op_type == "transform":
                # Non-deterministic: call Executor for each note
                async for proposal in self._run_executor_batch(
                    user_id, note_ids, params.get("instruction", ""),
                ):
                    proposals.append(proposal)
                    yield _format_sse_event(proposal, event="ai:proposal")
            else:
                # Deterministic batch
                proposals = await generate_deterministic_proposals(
                    self.db, user_id, confirmation,
                )
                for p in proposals:
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
            proposal_msg = await self.repo.add_message(
                session_id=session_id,
                role="assistant",
                content=f"Generated {len(proposals)} proposals from bulk {op_type}.",
                actions=proposals,
                token_estimate=_estimate_tokens(str(proposals)),
            )

        # Update confirmation summary
        n = len(note_ids)
        confirmation["summary"] = (
            f"{op_type} for {n} notes — confirmed, {len(proposals)} proposals generated"
        )
        await self.repo.update_message_actions(msg, msg.actions)

        yield _format_sse_event({}, event="ai:done")

    async def _run_executor_batch(
        self,
        user_id: uuid.UUID,
        note_ids: list[str],
        instruction: str,
    ) -> AsyncGenerator[dict]:
        """Call Executor (one-shot LLM) for each note in a batch_transform."""
        for raw_id in note_ids:
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
                logger.warning(
                    "Executor failed for note %s: %s", nid, exc,
                )
                continue

    async def _execute_single_note(
        self, note, instruction: str,
    ) -> list[dict]:
        """One-shot Executor call for a single note. Returns proposals."""
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
            pass  # We don't stream executor text

        proposals = []
        for tc in accumulator.tool_calls:
            try:
                args = json.loads(tc.arguments) if tc.arguments else {}
            except json.JSONDecodeError:
                continue

            if tc.name == "edit_note":
                title = args.get("title")
                content = args.get("content")
                if title or content:
                    proposals.append(make_proposal(
                        "edit_note", str(note.id),
                        {"title": title, "content": content},
                    ))
            elif tc.name == "add_tags":
                tags = args.get("tags", [])
                if tags:
                    proposals.append(make_proposal(
                        "add_tags", str(note.id), {"tags": tags},
                    ))
            elif tc.name == "remove_tags":
                tags = args.get("tags", [])
                if tags:
                    proposals.append(make_proposal(
                        "remove_tags", str(note.id), {"tags": tags},
                    ))
            elif tc.name == "delete_note":
                proposals.append(make_proposal(
                    "delete_note", str(note.id),
                    {"note_title": note.title or "Untitled"},
                ))

        return proposals

    # -----------------------------------------------------------------------
    # Dismiss bulk (AIS 6.3)
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
            session_id, confirmation_id,
        )
        if not msg or not confirmation:
            raise NotFoundError("Confirmation not found")
        if confirmation.get("status") != "pending":
            raise ConflictError("Confirmation already processed")

        confirmation["status"] = "dismissed"
        confirmation["summary"] = _build_summary(confirmation, "dismissed")
        msg = await self.repo.update_message_actions(msg, msg.actions)
        return MessageResponse.model_validate(msg)

    # -----------------------------------------------------------------------
    # Dismiss all pending in a session (AIS 10.2)
    # -----------------------------------------------------------------------

    async def _dismiss_all_pending(
        self, user_id: uuid.UUID, session_id: uuid.UUID,
    ) -> None:
        session = await self.repo.get_session(session_id, user_id)
        if not session:
            return

        messages = await self.repo.get_recent_messages(session_id, limit=100)
        for msg in messages:
            if not msg.actions or msg.role != "assistant":
                continue
            actions = msg.actions if isinstance(msg.actions, list) else [msg.actions]
            changed = False
            for a in actions:
                if a.get("status") == "pending":
                    a["status"] = "dismissed"
                    a["summary"] = _build_summary(a, "dismissed")
                    if a.get("type") == "proposal":
                        a["data"] = None
                    changed = True
            if changed:
                await self.repo.update_message_actions(msg, actions)

    # -----------------------------------------------------------------------
    # Build LLM messages (AIS 7)
    # -----------------------------------------------------------------------

    async def _build_llm_messages(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        note_ids: list[uuid.UUID],
    ) -> list[dict]:
        # System prompt
        system_content = PLANNER_SYSTEM_PROMPT.format(
            current_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        )
        messages: list[dict] = [{"role": "system", "content": system_content}]

        # History
        history = await self.repo.get_recent_messages(
            session_id, limit=settings.max_messages_in_context,
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

        for i, msg in enumerate(selected):
            msg_content = msg.content
            is_last_user = (
                msg.role == "user" and i == len(selected) - 1
            )

            # Append attached notes preview to the last user message (AIS 7.4)
            if is_last_user and note_ids:
                previews = await self._build_attached_previews(user_id, note_ids)
                if previews:
                    msg_content += "\n\n[Attached notes:]\n" + previews

            # Append actions summary to assistant messages (AIS 7.4)
            if msg.role == "assistant" and msg.actions:
                summary = _actions_summary_for_context(msg.actions)
                if summary:
                    msg_content += "\n\n" + summary

            messages.append({"role": msg.role, "content": msg_content})

        return messages

    async def _build_attached_previews(
        self, user_id: uuid.UUID, note_ids: list[uuid.UUID],
    ) -> str:
        notes = await self.notes_repo.get_notes_by_ids(note_ids, user_id)
        lines = []
        for n in notes[: settings.max_attached_notes]:
            if n.deleted_at is not None:
                continue
            preview = (n.content or "")[:100]
            lines.append(f"- {n.id} | {n.title or 'Untitled'}: {preview}")
        return "\n".join(lines)
