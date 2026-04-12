from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Final

import nh3
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.common.exceptions import ConflictError, NotFoundError, ValidationError
from src.app.config import settings
from src.app.modules.notes.models import Note
from src.app.modules.notes.repository import NotesRepository
from src.app.modules.notes.schemas import (
    BatchNotesResponse,
    NoteListItem,
    NoteListResponse,
    NoteResponse,
    TagBrief,
)
from src.app.modules.rag.service import RAGService
from src.app.modules.tags.repository import TagsRepository


class _Unset:
    """Sentinel for unset fields."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = _Unset()


def _sanitize(text: str | None) -> str | None:
    if text is None:
        return None
    return nh3.clean(text)


class NotesService:
    def __init__(self, db: AsyncSession):
        self.repo = NotesRepository(db)
        self.tags_repo = TagsRepository(db)
        self.rag = RAGService(db)

    def _note_to_response(self, note: Note) -> NoteResponse:
        return NoteResponse(
            id=note.id,
            user_id=note.user_id,
            title=note.title,
            content=note.content,
            version=note.version,
            created_at=note.created_at,
            updated_at=note.updated_at,
            deleted_at=note.deleted_at,
            tags=[TagBrief(id=t.id, name=t.name) for t in note.tags],
        )

    async def create(
        self,
        user_id: uuid.UUID,
        title: str | None,
        content: str | None,
        tag_ids: list[uuid.UUID],
    ) -> NoteResponse:
        count = await self.repo.count_user_notes(user_id)
        if count >= settings.max_notes_per_user:
            raise ConflictError("Note limit reached")

        if tag_ids:
            if len(tag_ids) > settings.max_tags_per_note:
                raise ValidationError(f"Maximum {settings.max_tags_per_note} tags per note")
            found = await self.tags_repo.verify_tags_belong_to_user(user_id, tag_ids)
            if len(found) != len(tag_ids):
                raise NotFoundError("One or more tags not found")

        title = _sanitize(title)
        content = _sanitize(content)

        note = await self.repo.create_note(user_id, title, content)

        if tag_ids:
            await self.repo.set_note_tags(note.id, tag_ids)

        note = await self.repo.get_active_note(note.id, user_id)

        if not note:
            raise RuntimeError("Failed to retrieve newly created note")

        await self.rag.index_note(note)
        return self._note_to_response(note)

    async def get(self, user_id: uuid.UUID, note_id: uuid.UUID) -> NoteResponse:
        note = await self.repo.get_note_by_id(note_id, user_id)
        if not note:
            raise NotFoundError("Note not found")
        else:
            return self._note_to_response(note)

    async def list(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        deleted: bool = False,
        search: str | None = None,
        tag_ids: list[uuid.UUID] | None = None,
    ) -> NoteListResponse:
        notes, total = await self.repo.list_notes(user_id, limit, offset, deleted, search, tag_ids)
        return NoteListResponse(
            items=[NoteListItem.model_validate(n) for n in notes],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def update(
        self,
        user_id: uuid.UUID,
        note_id: uuid.UUID,
        version: int,
        title: str | None | _Unset = UNSET,
        content: str | None | _Unset = UNSET,
    ) -> NoteResponse:
        note = await self.repo.get_active_note(note_id, user_id)
        if not note:
            raise NotFoundError("Note not found")

        if note.version != version:
            raise ConflictError("Version conflict — refresh and retry")

        if title is not UNSET:
            title = _sanitize(title)  # type: ignore
        else:
            title = note.title

        if content is not UNSET:
            content = _sanitize(content)  # type: ignore
        else:
            content = note.content

        note = await self.repo.update_note(note, title, content)
        await self.rag.index_note(note)
        return self._note_to_response(note)

    async def soft_delete(self, user_id: uuid.UUID, note_id: uuid.UUID) -> None:
        note = await self.repo.get_active_note(note_id, user_id)
        if not note:
            raise NotFoundError("Note not found")
        await self.repo.soft_delete_note(note, datetime.now(UTC))
        await self.rag.remove_note(note.id)

    async def restore(self, user_id: uuid.UUID, note_id: uuid.UUID) -> NoteResponse:
        note = await self.repo.get_deleted_note(note_id, user_id)
        if not note:
            raise NotFoundError("Note not found")
        note = await self.repo.restore_note(note)
        await self.rag.index_note(note)
        return self._note_to_response(note)

    async def hard_delete(self, user_id: uuid.UUID, note_id: uuid.UUID) -> None:
        note = await self.repo.get_deleted_note(note_id, user_id)
        if not note:
            raise NotFoundError("Note not found")
        await self.rag.remove_note(note.id)
        await self.repo.hard_delete_note(note)

    async def update_tags(
        self,
        user_id: uuid.UUID,
        note_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
    ) -> NoteResponse:
        note = await self.repo.get_active_note(note_id, user_id)
        if not note:
            raise NotFoundError("Note not found")

        if len(tag_ids) > settings.max_tags_per_note:
            raise ValidationError(f"Maximum {settings.max_tags_per_note} tags per note")

        if tag_ids:
            found = await self.tags_repo.verify_tags_belong_to_user(user_id, tag_ids)
            if len(found) != len(tag_ids):
                raise NotFoundError("One or more tags not found")

        await self.repo.set_note_tags(note.id, tag_ids)

        note = await self.repo.get_active_note(note_id, user_id)

        if not note:
            raise RuntimeError("Failed to retrieve newly created note")

        return self._note_to_response(note)

    async def batch_get(
        self,
        user_id: uuid.UUID,
        note_ids: list[uuid.UUID],
    ) -> BatchNotesResponse:
        notes = await self.repo.get_notes_by_ids(note_ids, user_id)
        return BatchNotesResponse(items=[self._note_to_response(n) for n in notes])
