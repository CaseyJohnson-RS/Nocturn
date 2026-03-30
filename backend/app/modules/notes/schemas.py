import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# --- Shared ---

class TagBrief(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


# --- Requests ---

class CreateNoteRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=20000)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class UpdateNoteRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=20000)
    version: int = Field(gt=0)


class UpdateNoteTagsRequest(BaseModel):
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class BatchGetNotesRequest(BaseModel):
    note_ids: list[uuid.UUID] = Field(max_length=50)


# --- Responses ---

class NoteResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    content: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    tags: list[TagBrief] = []

    model_config = {"from_attributes": True}


class NoteListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    updated_at: datetime
    deleted_at: datetime | None

    model_config = {"from_attributes": True}


class NoteListResponse(BaseModel):
    items: list[NoteListItem]
    total: int
    limit: int
    offset: int


class BatchNotesResponse(BaseModel):
    items: list[NoteResponse]
