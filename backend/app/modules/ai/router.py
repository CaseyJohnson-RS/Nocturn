import uuid

from fastapi import APIRouter, status
from starlette.responses import StreamingResponse

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.ai.schemas import (
    ConfirmActionRequest,
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
    UpdateSessionRequest,
)
from app.modules.ai.service import AIService

router = APIRouter(prefix="/api/ai", tags=["ai"])


# --- Sessions ---

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(body: CreateSessionRequest, user: AuthUser, db: DBSession):
    service = AIService(db)
    return await service.create_session(user.id, body.title)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(user: AuthUser, db: DBSession, limit: int = 50, offset: int = 0):
    service = AIService(db)
    return await service.list_sessions(user.id, limit, offset)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, user: AuthUser, db: DBSession):
    service = AIService(db)
    return await service.get_session(user.id, session_id)


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, body: UpdateSessionRequest, user: AuthUser, db: DBSession):
    service = AIService(db)
    return await service.update_session(user.id, session_id, body.title)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, user: AuthUser, db: DBSession):
    service = AIService(db)
    await service.delete_session(user.id, session_id)


# --- Chat (SSE streaming) ---

@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageRequest, user: AuthUser, db: DBSession):
    """Send a message and stream the AI response as Server-Sent Events."""
    service = AIService(db)

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


@router.post(
    "/sessions/{session_id}/messages/{message_id}/actions/confirm",
    response_model=MessageResponse,
)
async def confirm_action(
    session_id: uuid.UUID,
    message_id: uuid.UUID,
    body: ConfirmActionRequest,
    user: AuthUser,
    db: DBSession,
):
    service = AIService(db)
    return await service.confirm_action(
        user.id,
        session_id,
        message_id,
        body.action_index,
        body.approved,
    )
