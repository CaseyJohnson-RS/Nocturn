import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Requests ---

class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    note_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)


class ConfirmActionRequest(BaseModel):
    action_index: int = Field(ge=0)
    approved: bool = Field(default=True)


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class UpdateSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


# --- Responses ---

class MessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    sources: str | None = None
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
