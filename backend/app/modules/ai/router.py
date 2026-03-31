"""AI assistant router — AIS-compliant endpoints."""

import uuid

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.ai.schemas import (
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    UpdateActionRequest,
    UpdateSessionRequest,
)
from app.modules.ai.service import AIService

router = APIRouter(prefix="/api/ai", tags=["ai"])


# --- Sessions ---

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(body: CreateSessionRequest, user: AuthUser, db: DBSession):
    service = AIService(db)
    return await service.create_session(user.id, body.title, body.dismiss_session_id)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(user: AuthUser, db: DBSession, limit: int = 50, offset: int = 0):
    service = AIService(db)
    return await service.list_sessions(user.id, limit, offset)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: uuid.UUID, user: AuthUser, db: DBSession):
    service = AIService(db)
    return await service.get_session(user.id, session_id)


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID, body: UpdateSessionRequest, user: AuthUser, db: DBSession,
):
    service = AIService(db)
    return await service.update_session(user.id, session_id, body.title)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, user: AuthUser, db: DBSession):
    service = AIService(db)
    await service.delete_session(user.id, session_id)


# --- Chat (SSE streaming) ---

@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID, body: SendMessageRequest, user: AuthUser, db: DBSession,
):
    """Send a message and stream the AI response as Server-Sent Events."""
    service = AIService(db)

    # Validate before starting SSE — return JSON errors instead of raising
    # inside a generator (which would fail after SSE headers are sent).
    error = await service.pre_validate_send(user.id, session_id, body.message)
    if error:
        return JSONResponse(
            status_code=error[0],
            content={"detail": error[1]},
        )

    async def event_stream():
        async for chunk in service.send_message(
            user.id, session_id, body.message, body.note_ids,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# --- Cancel (AIS 9.3) ---

@router.post("/sessions/{session_id}/cancel")
async def cancel_generation(
    session_id: uuid.UUID, user: AuthUser, db: DBSession,
):
    service = AIService(db)
    return await service.cancel_generation(user.id, session_id)


# --- Proposal lifecycle (AIS 9.4) ---

@router.patch(
    "/sessions/{session_id}/messages/{message_id}/actions/{action_id}",
    response_model=MessageResponse,
)
async def update_action(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    action_id: str,
    body: UpdateActionRequest,
    user: AuthUser,
    db: DBSession,
):
    """Apply or dismiss a single proposal."""
    service = AIService(db)
    return await service.update_action_status(
        user.id, session_id, message_id, action_id, body.status,
    )


# --- Bulk confirmation (AIS 9.4) ---

@router.post("/sessions/{session_id}/confirm/{confirmation_id}")
async def confirm_bulk(
    session_id: uuid.UUID,
    confirmation_id: str,
    user: AuthUser,
    db: DBSession,
):
    """Confirm a pending bulk operation and stream generated proposals."""
    service = AIService(db)

    async def event_stream():
        async for chunk in service.confirm_bulk(
            user.id, session_id, confirmation_id,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/sessions/{session_id}/dismiss/{confirmation_id}",
    response_model=MessageResponse,
)
async def dismiss_bulk(
    session_id: uuid.UUID,
    confirmation_id: str,
    user: AuthUser,
    db: DBSession,
):
    """Dismiss a pending bulk operation."""
    service = AIService(db)
    return await service.dismiss_bulk(user.id, session_id, confirmation_id)
