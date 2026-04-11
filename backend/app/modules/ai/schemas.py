import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# --- Requests ---


class SendMessageRequest(BaseModel):
    """POST /api/ai/sessions/{id}/messages (AIS 9.2)."""

    content: str = Field(min_length=1, max_length=4000)
    attached_note_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)  # type: ignore[call-overload]


class CreateSessionRequest(BaseModel):
    """POST /api/ai/sessions (AIS 10.2)."""

    dismiss_session_id: uuid.UUID | None = Field(default=None)


class UpdateSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class UpdateActionRequest(BaseModel):
    """PATCH /actions/{action_id} — apply or dismiss a proposal (AIS 9.4)."""

    status: str = Field(pattern=r"^(applied|dismissed)$")


# --- Responses ---


class MessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    actions: list[dict] | None = None  # type: ignore[type-arg]
    attached_note_ids: list[uuid.UUID] | None = None
    created_at: datetime


class SessionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    created_at: datetime
    last_message_at: datetime | None


class SessionListResponse(BaseModel):
    items: list[SessionResponse]
    total: int


class MessagesListResponse(BaseModel):
    """GET /api/ai/sessions/{id}/messages — paginated (AIS 9.1)."""

    items: list[MessageResponse]
    total: int
