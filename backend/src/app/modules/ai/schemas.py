import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# --- Requests ---


class SendMessageRequest(BaseModel):
    """User message to send to the AI assistant."""

    content: str = Field(min_length=1, max_length=4000, description="Message text (1–4000 chars)")
    attached_note_ids: list[uuid.UUID] = Field(  # type: ignore
        default_factory=list,
        max_length=5,
        description=(
            "Note IDs to attach as context for the AI (max 5). "
            "Their content is included in the LLM prompt."
        ),
    )


class CreateSessionRequest(BaseModel):
    """Payload for creating a new chat session."""

    dismiss_session_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Optional: ID of a previous session to dismiss (soft-delete) "
            "atomically. Useful for 'New chat' flows."
        ),
    )


class UpdateSessionRequest(BaseModel):
    """Payload for renaming a chat session."""

    title: str = Field(min_length=1, max_length=200, description="New session title (1–200 chars)")


class UpdateActionRequest(BaseModel):
    """Apply or dismiss a single AI proposal."""

    status: str = Field(
        pattern=r"^(applied|dismissed)$",
        description="New status: `applied` (execute the action) or `dismissed` (reject it)",
    )


# --- Responses ---


class MessageResponse(BaseModel):
    """Chat message (user or assistant)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID = Field(description="Message ID")
    session_id: uuid.UUID = Field(description="Parent session ID")
    role: str = Field(description="Message role: `user` or `assistant`")
    content: str = Field(description="Message text content")
    actions: list[dict] | None = Field(  # type: ignore[type-arg]
        default=None,
        description=(
            "List of AI actions attached to an assistant message. "
            "Each action is either a **proposal** (`type: 'proposal'`) with fields: "
            "`id`, `proposal_type` (edit_note/create_note/delete_note/add_tags/remove_tags), "
            "`status` (pending/applied/dismissed), `note_id`, `data`, `summary`; "
            "or a **pending_confirmation** (`type: 'pending_confirmation'`) with fields: "
            "`id`, `status` (pending/confirmed/dismissed), `operation_type`, `note_ids`, `params`, "
            "`summary`. `null` for user messages."
        ),
    )
    attached_note_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Note IDs that were attached to a user message as context. `null` if none.",
    )
    created_at: datetime = Field(description="Message timestamp (UTC)")


class SessionResponse(BaseModel):
    """Chat session metadata."""

    model_config = {"from_attributes": True}

    id: uuid.UUID = Field(description="Session ID")
    user_id: uuid.UUID = Field(description="Owner user ID")
    title: str | None = Field(description="Session title (auto-set from first message, or `null`)")
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    last_message_at: datetime | None = Field(
        description="Timestamp of the last message in this session, or `null`"
    )


class SessionListResponse(BaseModel):
    """Paginated list of chat sessions."""

    items: list[SessionResponse] = Field(description="Sessions on this page")
    total: int = Field(description="Total number of sessions")


class MessagesListResponse(BaseModel):
    """Paginated list of messages in a session."""

    items: list[MessageResponse] = Field(description="Messages on this page (chronological order)")
    total: int = Field(description="Total number of messages in the session")
