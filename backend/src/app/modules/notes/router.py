import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.app.common.dependencies import DBSession
from src.app.middleware.auth import AuthUser
from src.app.modules.notes.schemas import (
    BatchGetNotesRequest,
    BatchNotesResponse,
    CreateNoteRequest,
    NoteListResponse,
    NoteResponse,
    UpdateNoteRequest,
    UpdateNoteTagsRequest,
)
from src.app.modules.notes.service import NotesService

router = APIRouter(prefix="/api/notes", tags=["notes"])


async def get_notes_service(db: DBSession) -> NotesService:
    return NotesService(db)


NotesServiceDep = Annotated[NotesService, Depends(get_notes_service)]


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a note",
)
async def create_note(body: CreateNoteRequest, user: AuthUser, service: NotesServiceDep):
    """Create a new note with optional title, content, and tags.

    The note is created with `version = 1`. If `tag_ids` are provided,
    they are linked to the note immediately (maximum 10 tags per note).

    Returns the full note object including generated `id` and timestamps.
    """
    return await service.create(user.id, body.title, body.content, body.tag_ids)


@router.get(
    "",
    response_model=NoteListResponse,
    summary="List notes",
)
async def list_notes(
    user: AuthUser,
    service: NotesServiceDep,
    limit: int = Query(default=50, ge=1, le=200, description="Max number of notes to return"),
    offset: int = Query(default=0, ge=0, description="Number of notes to skip"),
    deleted: bool = Query(
        default=False, description="If `true`, return only soft-deleted notes (trash)"
    ),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Full-text search query (matches title and content)",
    ),
    tag_ids: str | None = Query(
        default=None, description="Comma-separated tag UUIDs to filter by (AND logic)"
    ),
):
    """Return a paginated list of the user's notes.

    By default only active (non-deleted) notes are returned, sorted by
    `updated_at` descending. Pass `deleted=true` to list trashed notes.

    Supports full-text search via `search` and tag-based filtering via
    `tag_ids` (comma-separated UUIDs — only notes having **all** listed
    tags are returned).
    """
    parsed_tag_ids = None
    if tag_ids:
        parsed_tag_ids = [uuid.UUID(tid.strip()) for tid in tag_ids.split(",")]

    return await service.list(user.id, limit, offset, deleted, search, parsed_tag_ids)


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get a note",
    responses={404: {"description": "Note not found or does not belong to user"}},
)
async def get_note(note_id: uuid.UUID, user: AuthUser, service: NotesServiceDep):
    """Return the full note object including content, tags, and version.

    Works for both active and soft-deleted notes.
    """
    return await service.get(user.id, note_id)


@router.put(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update a note",
    responses={
        404: {"description": "Note not found"},
        409: {"description": "Version conflict — the note was modified by another request"},
    },
)
async def update_note(
    note_id: uuid.UUID,
    body: UpdateNoteRequest,
    user: AuthUser,
    service: NotesServiceDep,
):
    """Update a note's title and/or content.

    Uses **optimistic concurrency control**: the client must send the
    current `version` of the note. If the server's version differs,
    a `409 Conflict` is returned and the client should re-fetch the
    note before retrying.

    On success the `version` is incremented by one.
    Only fields present in the request body are updated (partial update).
    """
    payload = body.model_dump(exclude_unset=True)
    kwargs: dict[str, object] = {"version": payload["version"]}
    if "title" in payload:
        kwargs["title"] = payload["title"]
    if "content" in payload:
        kwargs["content"] = payload["content"]
    return await service.update(user.id, note_id, **kwargs)  # type: ignore


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
    responses={404: {"description": "Note not found"}},
)
async def delete_note(
    note_id: uuid.UUID,
    user: AuthUser,
    service: NotesServiceDep,
    permanent: bool = Query(
        default=False,
        description=(
            "If `true`, permanently remove the note. Otherwise move it to trash (soft-delete)."
        ),
    ),
):
    """Delete a note.

    **Soft-delete** (default): sets `deleted_at` timestamp.
    The note can later be restored via `POST /{note_id}/restore`.

    **Permanent delete** (`permanent=true`): irreversibly removes the
    note and all associated data (embeddings, tag links).
    """
    if permanent:
        await service.hard_delete(user.id, note_id)
    else:
        await service.soft_delete(user.id, note_id)


@router.post(
    "/{note_id}/restore",
    response_model=NoteResponse,
    summary="Restore a deleted note",
    responses={
        404: {"description": "Note not found"},
        400: {"description": "Note is not deleted"},
    },
)
async def restore_note(note_id: uuid.UUID, user: AuthUser, service: NotesServiceDep):
    """Restore a soft-deleted note from trash.

    Clears the `deleted_at` timestamp and returns the restored note.
    Has no effect if the note was permanently deleted.
    """
    return await service.restore(user.id, note_id)


@router.put(
    "/{note_id}/tags",
    response_model=NoteResponse,
    summary="Set note tags",
    responses={404: {"description": "Note or tag not found"}},
)
async def update_note_tags(
    note_id: uuid.UUID,
    body: UpdateNoteTagsRequest,
    user: AuthUser,
    service: NotesServiceDep,
):
    """Replace the note's tag set with the provided list.

    Pass an empty `tag_ids` array to remove all tags.
    Maximum 10 tags per note.

    Returns the updated note with the new `tags` list.
    """
    return await service.update_tags(user.id, note_id, body.tag_ids)


@router.post(
    "/batch",
    response_model=BatchNotesResponse,
    summary="Get multiple notes",
)
async def batch_get_notes(body: BatchGetNotesRequest, user: AuthUser, service: NotesServiceDep):
    """Fetch multiple notes by their IDs in a single request.

    Useful for resolving `attached_note_ids` from chat messages.
    Notes that don't exist or belong to another user are silently
    skipped. Maximum 50 IDs per request.
    """
    return await service.batch_get(user.id, body.note_ids)
