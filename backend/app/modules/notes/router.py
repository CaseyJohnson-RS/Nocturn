import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.notes.schemas import (
    BatchGetNotesRequest,
    BatchNotesResponse,
    CreateNoteRequest,
    NoteListResponse,
    NoteResponse,
    UpdateNoteRequest,
    UpdateNoteTagsRequest,
)
from app.modules.notes.service import NotesService

router = APIRouter(prefix="/api/notes", tags=["notes"])


async def get_notes_service(db: DBSession) -> NotesService:
    return NotesService(db)


NotesServiceDep = Annotated[NotesService, Depends(get_notes_service)]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(body: CreateNoteRequest, user: AuthUser, service: NotesServiceDep):
    return await service.create(user.id, body.title, body.content, body.tag_ids)


@router.get("", response_model=NoteListResponse)
async def list_notes(
    user: AuthUser,
    service: NotesServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    deleted: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=200),
    tag_ids: str | None = Query(default=None, description="Comma-separated tag UUIDs"),
):
    parsed_tag_ids = None
    if tag_ids:
        parsed_tag_ids = [uuid.UUID(tid.strip()) for tid in tag_ids.split(",")]

    return await service.list(user.id, limit, offset, deleted, search, parsed_tag_ids)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: uuid.UUID, user: AuthUser, service: NotesServiceDep):
    return await service.get(user.id, note_id)


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: uuid.UUID,
    body: UpdateNoteRequest,
    user: AuthUser,
    service: NotesServiceDep,
):
    payload = body.model_dump(exclude_unset=True)
    kwargs: dict[str, object] = {"version": payload["version"]}
    if "title" in payload:
        kwargs["title"] = payload["title"]
    if "content" in payload:
        kwargs["content"] = payload["content"]
    return await service.update(user.id, note_id, **kwargs)  # type: ignore


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    user: AuthUser,
    service: NotesServiceDep,
    permanent: bool = Query(default=False),
):
    if permanent:
        await service.hard_delete(user.id, note_id)
    else:
        await service.soft_delete(user.id, note_id)


@router.post("/{note_id}/restore", response_model=NoteResponse)
async def restore_note(note_id: uuid.UUID, user: AuthUser, service: NotesServiceDep):
    return await service.restore(user.id, note_id)


@router.put("/{note_id}/tags", response_model=NoteResponse)
async def update_note_tags(
    note_id: uuid.UUID,
    body: UpdateNoteTagsRequest,
    user: AuthUser,
    service: NotesServiceDep,
):
    return await service.update_tags(user.id, note_id, body.tag_ids)


@router.post("/batch", response_model=BatchNotesResponse)
async def batch_get_notes(body: BatchGetNotesRequest, user: AuthUser, service: NotesServiceDep):
    return await service.batch_get(user.id, body.note_ids)
