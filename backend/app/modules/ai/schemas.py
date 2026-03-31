import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Requests ---

class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    note_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    dismiss_session_id: uuid.UUID | None = Field(
        default=None,
        description="If set, dismiss all pending proposals in this session before creating a new one",
    )


class UpdateSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class UpdateActionRequest(BaseModel):
    """PATCH /actions/{action_id} — apply or dismiss a proposal."""
    status: str = Field(pattern=r"^(applied|dismissed)$")


# --- Responses ---

class MessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    actions: list[dict] | dict | None = None
    attached_note_ids: list[uuid.UUID] | None = None
    token_estimate: int
    created_at: datetime


class SessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse]


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int
