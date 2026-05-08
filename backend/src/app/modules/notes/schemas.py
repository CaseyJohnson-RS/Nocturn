import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# --- Shared ---


class TagBrief(BaseModel):
    """Minimal tag representation attached to a note."""

    id: uuid.UUID = Field(description="Tag ID")
    name: str = Field(description="Tag display name")

    model_config = {"from_attributes": True}


# --- Requests ---


class CreateNoteRequest(BaseModel):
    """Payload for creating a new note."""

    title: str | None = Field(
        default=None, max_length=200, description="Note title (max 200 chars). `null` for untitled."
    )
    content: str | None = Field(
        default=None, max_length=20000, description="Markdown content (max 20 000 chars)"
    )
    tag_ids: list[uuid.UUID] = Field(  # type: ignore
        default_factory=list, max_length=10, description="Tag IDs to attach (max 10)"
    )


class UpdateNoteRequest(BaseModel):
    """Payload for updating a note. Only provided fields are changed."""

    title: str | None = Field(
        default=None, max_length=200, description="New title (or `null` to clear)"
    )
    content: str | None = Field(
        default=None, max_length=20000, description="New content (or `null` to clear)"
    )
    version: int = Field(
        gt=0,
        description="Current note version for optimistic concurrency. "
        "Must match the server's version or 409 is returned.",
    )


class UpdateNoteTagsRequest(BaseModel):
    """Replace the note's entire tag set."""

    tag_ids: list[uuid.UUID] = Field(  # type: ignore
        default_factory=list,
        max_length=10,
        description="New tag IDs (replaces all existing). Pass `[]` to remove all tags.",
    )


class BatchGetNotesRequest(BaseModel):
    """Fetch multiple notes in one request."""

    note_ids: list[uuid.UUID] = Field(
        max_length=50, description="List of note IDs to fetch (max 50)"
    )


# --- Responses ---


class NoteResponse(BaseModel):
    """Full note object."""

    id: uuid.UUID = Field(description="Note ID")
    user_id: uuid.UUID = Field(description="Owner user ID")
    title: str | None = Field(description="Note title or `null`")
    content: str | None = Field(description="Markdown content or `null`")
    version: int = Field(
        description="Monotonically increasing version number for optimistic concurrency"
    )
    created_at: datetime = Field(description="Creation timestamp (UTC)")
    updated_at: datetime = Field(description="Last modification timestamp (UTC)")
    deleted_at: datetime | None = Field(description="Soft-delete timestamp or `null` if active")
    tags: list[TagBrief] = Field(default=[], description="Tags attached to this note")

    model_config = {"from_attributes": True}


class NoteListItem(BaseModel):
    """Lightweight note representation for list views."""

    id: uuid.UUID = Field(description="Note ID")
    title: str | None = Field(description="Note title or `null`")
    updated_at: datetime = Field(description="Last modification timestamp (UTC)")
    deleted_at: datetime | None = Field(description="Soft-delete timestamp or `null`")
    tags: list[TagBrief] = Field(default=[], description="Tags attached to this note")

    model_config = {"from_attributes": True}


class NoteListResponse(BaseModel):
    """Paginated list of notes."""

    items: list[NoteListItem] = Field(description="Notes on this page")
    total: int = Field(description="Total number of matching notes")
    limit: int = Field(description="Requested page size")
    offset: int = Field(description="Requested offset")


class NoteSearchResponse(BaseModel):
    """Result of a keyword search over notes."""

    items: list[NoteListItem] = Field(description="Matching notes")
    total: int = Field(description="Total number of matching notes")
    limit: int = Field(description="Applied result limit")
    keywords: list[str] = Field(description="Keywords used in the search")


class BatchNotesResponse(BaseModel):
    """Batch of full note objects."""

    items: list[NoteResponse] = Field(
        description="Requested notes (missing/inaccessible IDs are silently skipped)"
    )
