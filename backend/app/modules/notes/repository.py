import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.notes.models import Note, NoteTag
from app.modules.tags.models import Tag


class NotesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_note(
        self,
        user_id: uuid.UUID,
        title: str | None,
        content: str | None,
    ) -> Note:
        note = Note(user_id=user_id, title=title, content=content)
        self.db.add(note)
        await self.db.flush()
        return note

    async def get_note_by_id(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id == note_id, Note.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active_note(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id == note_id, Note.user_id == user_id, Note.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_deleted_note(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id == note_id, Note.user_id == user_id, Note.deleted_at.is_not(None))
        )
        return result.scalar_one_or_none()

    async def list_notes(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        deleted: bool = False,
        search: str | None = None,
        tag_ids: list[uuid.UUID] | None = None,
    ) -> tuple[list[Note], int]:
        query = select(Note).where(Note.user_id == user_id)
        count_query = select(func.count(Note.id)).where(Note.user_id == user_id)

        if deleted:
            query = query.where(Note.deleted_at.is_not(None))
            count_query = count_query.where(Note.deleted_at.is_not(None))
        else:
            query = query.where(Note.deleted_at.is_(None))
            count_query = count_query.where(Note.deleted_at.is_(None))

        if search:
            pattern = f"%{search}%"
            search_filter = Note.title.ilike(pattern) | Note.content.ilike(pattern)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        if tag_ids:
            query = query.where(
                Note.id.in_(
                    select(NoteTag.note_id).where(NoteTag.tag_id.in_(tag_ids))
                )
            )
            count_query = count_query.where(
                Note.id.in_(
                    select(NoteTag.note_id).where(NoteTag.tag_id.in_(tag_ids))
                )
            )

        query = query.order_by(Note.updated_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        notes = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return notes, total

    async def update_note(
        self,
        note: Note,
        title: str | None,
        content: str | None,
    ) -> Note:
        note.title = title
        note.content = content
        note.version += 1
        note.updated_at = func.now()
        await self.db.flush()
        await self.db.refresh(note)
        return note

    async def soft_delete_note(self, note: Note, now: datetime) -> None:
        note.deleted_at = now
        await self.db.flush()

    async def restore_note(self, note: Note) -> Note:
        note.deleted_at = None
        await self.db.flush()
        await self.db.refresh(note, attribute_names=["tags"])
        return note

    async def hard_delete_note(self, note: Note) -> None:
        await self.db.delete(note)
        await self.db.flush()

    async def set_note_tags(self, note_id: uuid.UUID, tag_ids: list[uuid.UUID]) -> None:
        await self.db.execute(delete(NoteTag).where(NoteTag.note_id == note_id))
        for tag_id in tag_ids:
            self.db.add(NoteTag(note_id=note_id, tag_id=tag_id))
        await self.db.flush()

    async def count_user_notes(self, user_id: uuid.UUID) -> int:
        """Count all notes including soft-deleted."""
        result = await self.db.execute(
            select(func.count(Note.id)).where(Note.user_id == user_id)
        )
        return result.scalar_one()

    async def get_notes_by_ids(
        self, note_ids: list[uuid.UUID], user_id: uuid.UUID
    ) -> list[Note]:
        if not note_ids:
            return []
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id.in_(note_ids), Note.user_id == user_id)
        )
        return list(result.scalars().all())
