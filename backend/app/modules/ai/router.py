"""AI assistant router."""

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


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(body: CreateSessionRequest, user: AuthUser, service: AIServiceDep):
    return await service.create_session(user.id, body.dismiss_session_id)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user: AuthUser,
    service: AIServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await service.list_sessions(user.id, limit, offset)


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    body: UpdateSessionRequest,
    user: AuthUser,
    service: AIServiceDep,
):
    return await service.update_session(user.id, session_id, body.title)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, user: AuthUser, service: AIServiceDep):
    await service.delete_session(user.id, session_id)


# endregion
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# region Messages


@router.get("/sessions/{session_id}/messages", response_model=MessagesListResponse)
async def get_messages(
    session_id: uuid.UUID,
    user: AuthUser,
    service: AIServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await service.get_messages(user.id, session_id, limit, offset)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user: AuthUser,
    service: AIServiceDep,
):
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


@router.post("/sessions/{session_id}/cancel")
async def cancel_generation(session_id: uuid.UUID, user: AuthUser, service: AIServiceDep):
    return await service.cancel_generation(user.id, session_id)


# --- Proposals ---


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
    service: AIServiceDep,
):
    return await service.update_action_status(
        user.id,
        session_id,
        message_id,
        action_id,
        body.status,
    )


# --- Bulk ---


@router.post("/sessions/{session_id}/confirm/{confirmation_id}")
async def confirm_bulk(
    session_id: uuid.UUID,
    confirmation_id: str,
    user: AuthUser,
    service: AIServiceDep,
):
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
)
async def dismiss_bulk(
    session_id: uuid.UUID,
    confirmation_id: str,
    user: AuthUser,
    service: AIServiceDep,
):
    return await service.dismiss_bulk(user.id, session_id, confirmation_id)


# endregion
# ---------------------------------------------------------------------------
