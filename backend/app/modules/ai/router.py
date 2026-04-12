"""AI assistant router — chat sessions, messaging with SSE streaming, proposals."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.ai.schemas import (
    CreateSessionRequest,
    MessageResponse,
    MessagesListResponse,
    SendMessageRequest,
    SessionListResponse,
    SessionResponse,
    UpdateActionRequest,
    UpdateSessionRequest,
)
from app.modules.ai.service import AIService

router = APIRouter(prefix="/api/ai", tags=["ai"])


async def get_ai_service(db: DBSession) -> AIService:
    return AIService(db)


AIServiceDep = Annotated[AIService, Depends(get_ai_service)]


# ---------------------------------------------------------------------------
# region Sessions


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a chat session",
)
async def create_session(body: CreateSessionRequest, user: AuthUser, service: AIServiceDep):
    """Create a new AI chat session.

    Optionally pass `dismiss_session_id` to dismiss (soft-delete) a
    previous session in the same request — useful for "New chat" flows
    where the old empty session should be cleaned up.

    The session is created with `title = null`; it is auto-titled after
    the first user message (first 100 characters).
    """
    return await service.create_session(user.id, body.dismiss_session_id)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List chat sessions",
)
async def list_sessions(
    user: AuthUser,
    service: AIServiceDep,
    limit: int = Query(default=50, ge=1, le=100, description="Max number of sessions"),
    offset: int = Query(default=0, ge=0, description="Number of sessions to skip"),
):
    """Return a paginated list of the user's chat sessions.

    Sorted by `last_message_at` descending (most recent first).
    """
    return await service.list_sessions(user.id, limit, offset)


@router.put(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    summary="Rename a chat session",
    responses={404: {"description": "Session not found"}},
)
async def update_session(
    session_id: uuid.UUID,
    body: UpdateSessionRequest,
    user: AuthUser,
    service: AIServiceDep,
):
    """Update the session title (1–200 characters)."""
    return await service.update_session(user.id, session_id, body.title)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
    responses={404: {"description": "Session not found"}},
)
async def delete_session(session_id: uuid.UUID, user: AuthUser, service: AIServiceDep):
    """Permanently delete a session and all its messages."""
    await service.delete_session(user.id, session_id)


# endregion
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# region Messages


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessagesListResponse,
    summary="Get session messages",
    responses={404: {"description": "Session not found"}},
)
async def get_messages(
    session_id: uuid.UUID,
    user: AuthUser,
    service: AIServiceDep,
    limit: int = Query(default=50, ge=1, le=200, description="Max number of messages"),
    offset: int = Query(default=0, ge=0, description="Number of messages to skip"),
):
    """Return paginated messages for a session.

    Messages are sorted chronologically (oldest first).
    Each assistant message may include an `actions` array with
    proposals and pending confirmations.
    """
    return await service.get_messages(user.id, session_id, limit, offset)


@router.post(
    "/sessions/{session_id}/messages",
    summary="Send a message (SSE stream)",
    responses={
        200: {
            "description": "SSE event stream (`text/event-stream`)",
            "content": {"text/event-stream": {}},
        },
        400: {"description": "Validation error (empty content, too many attachments, etc.)"},
        404: {"description": "Session not found"},
        409: {"description": "Another generation is already in progress for this session"},
    },
)
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user: AuthUser,
    service: AIServiceDep,
):
    """Send a user message and stream the AI assistant's response via SSE.

    **Pre-validation** runs before the stream starts and may return a
    regular JSON error response (400/404/409) — the client should check
    the `Content-Type` header to distinguish JSON from SSE.

    **SSE event types** (each `data` payload is JSON):

    | Event | Payload | Description |
    |---|---|---|
    | `ai:text_delta` | `{"delta": "..."}` | Incremental text chunk |
    | `ai:proposal` | `{Proposal object}` | A proposed note action (edit/create/delete/add_tags/remove_tags) |
    | `ai:pending_confirmation` | `{PendingConfirmation}` | Bulk operation awaiting user confirmation |
    | `ai:error` | `{"code": "...", "message": "..."}` | Error during generation (e.g. `"conflict"`) |
    | `ai:done` | `{"message": {Message}}` | Stream complete — contains the full saved assistant message |

    **Concurrency**: only one generation per session is allowed at a time.
    A Redis lock (`generating:{session_id}`) enforces this — a second
    request returns `409`.

    **Cancellation**: call `POST /cancel` to abort a running generation.

    **Attached notes**: up to 5 note IDs can be attached. Their content
    is included in the LLM context so the AI can reference them.
    """  # noqa: E501
    error = await service.pre_validate_send(user.id, session_id, body.content)
    if error:
        return JSONResponse(status_code=error[0], content={"detail": error[1]})

    async def event_stream():
        async for chunk in service.send_message(
            user.id,
            session_id,
            body.content,
            body.attached_note_ids,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Cancel ---


@router.post(
    "/sessions/{session_id}/cancel",
    summary="Cancel generation",
    responses={
        200: {"description": "Cancellation signal sent"},
        404: {"description": "Session not found"},
    },
)
async def cancel_generation(session_id: uuid.UUID, user: AuthUser, service: AIServiceDep):
    """Signal the server to stop an ongoing AI generation for this session.

    Sets a Redis key (`cancel:{session_id}`) which is polled between
    tool-calling rounds. The active SSE stream will end with an
    `ai:done` event shortly after.

    Safe to call even if no generation is in progress (no-op).
    """
    return await service.cancel_generation(user.id, session_id)


# --- Proposals ---


@router.patch(
    "/sessions/{session_id}/messages/{message_id}/actions/{action_id}",
    response_model=MessageResponse,
    summary="Apply or dismiss a proposal",
    responses={
        404: {"description": "Session, message, or action not found"},
        400: {"description": "Action already finalized or invalid status transition"},
    },
)
async def update_action(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    action_id: str,
    body: UpdateActionRequest,
    user: AuthUser,
    service: AIServiceDep,
):
    """Update the status of a single AI proposal.

    **Status transitions:**
    - `"applied"` — execute the proposed action (edit note, create note,
      delete note, add/remove tags). The action is carried out immediately
      and the status changes to `applied`.
    - `"dismissed"` — reject the proposal without executing it.

    Returns the full updated message (with all actions in their current state).

    Each proposal can only be finalized once — attempting to change an
    already-applied or already-dismissed proposal returns `400`.
    """
    return await service.update_action_status(
        user.id,
        session_id,
        message_id,
        action_id,
        body.status,
    )


# --- Bulk ---


@router.post(
    "/sessions/{session_id}/confirm/{confirmation_id}",
    summary="Confirm a bulk operation (SSE stream)",
    responses={
        200: {
            "description": "SSE event stream with individual proposals",
            "content": {"text/event-stream": {}},
        },
        404: {"description": "Session or confirmation not found"},
        400: {"description": "Confirmation already processed"},
    },
)
async def confirm_bulk(
    session_id: uuid.UUID,
    confirmation_id: str,
    user: AuthUser,
    service: AIServiceDep,
):
    """Confirm a pending bulk operation and stream back the individual proposals.

    When the AI suggests a bulk action (e.g. "add tag X to 10 notes"),
    it creates a `pending_confirmation` action. The user can either
    confirm (this endpoint) or dismiss (`POST /dismiss`).

    On confirmation, the server processes each note and streams back
    individual `ai:proposal` events via SSE, followed by `ai:done`
    with the updated message.
    """
    error = await service.pre_validate_confirm(user.id, session_id, confirmation_id)
    if error:
        return JSONResponse(status_code=error[0], content={"detail": error[1]})

    async def event_stream():
        async for chunk in service.confirm_bulk(user.id, session_id, confirmation_id):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/sessions/{session_id}/dismiss/{confirmation_id}",
    response_model=MessageResponse,
    summary="Dismiss a bulk operation",
    responses={
        404: {"description": "Session or confirmation not found"},
        400: {"description": "Confirmation already processed"},
    },
)
async def dismiss_bulk(
    session_id: uuid.UUID,
    confirmation_id: str,
    user: AuthUser,
    service: AIServiceDep,
):
    """Dismiss a pending bulk operation without executing it.

    Sets the confirmation status to `dismissed` and returns
    the updated message.
    """
    return await service.dismiss_bulk(user.id, session_id, confirmation_id)


# endregion
# ---------------------------------------------------------------------------
