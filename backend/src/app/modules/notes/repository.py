import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.modules.notes.models import Note, NoteTag


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
            .execution_options(populate_existing=True)
            .where(Note.id == note_id, Note.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active_note(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .execution_options(populate_existing=True)
            .where(Note.id == note_id, Note.user_id == user_id, Note.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_deleted_note(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None:
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .execution_options(populate_existing=True)
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
        exclude_tag_ids: list[uuid.UUID] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
    ) -> tuple[list[Note], int]:
        query = select(Note).options(selectinload(Note.tags)).where(Note.user_id == user_id)
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
            tag_filter = Note.id.in_(
                select(NoteTag.note_id).where(NoteTag.tag_id.in_(tag_ids))
            )
            query = query.where(tag_filter)
            count_query = count_query.where(tag_filter)

        if exclude_tag_ids:
            exclude_filter = Note.id.not_in(
                select(NoteTag.note_id).where(NoteTag.tag_id.in_(exclude_tag_ids))
            )
            query = query.where(exclude_filter)
            count_query = count_query.where(exclude_filter)

        if created_from:
            query = query.where(Note.created_at >= created_from)
            count_query = count_query.where(Note.created_at >= created_from)
        if created_to:
            query = query.where(Note.created_at <= created_to)
            count_query = count_query.where(Note.created_at <= created_to)
        if updated_from:
            query = query.where(Note.updated_at >= updated_from)
            count_query = count_query.where(Note.updated_at >= updated_from)
        if updated_to:
            query = query.where(Note.updated_at <= updated_to)
            count_query = count_query.where(Note.updated_at <= updated_to)

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
        # Re-query to properly load relationships (refresh doesn't work for async relationships)
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .execution_options(populate_existing=True)
            .where(Note.id == note.id)
        )
        return result.scalar_one()

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

    async def search_by_keywords(
        self,
        user_id: uuid.UUID,
        keywords: list[str],
        limit: int = 50,
    ) -> tuple[list[Note], int]:
        base_condition = (Note.user_id == user_id, Note.deleted_at.is_(None))
        query = select(Note).options(selectinload(Note.tags)).where(*base_condition)
        count_query = select(func.count(Note.id)).where(*base_condition)

        for keyword in keywords:
            pattern = f"%{keyword}%"
            kw_filter = Note.title.ilike(pattern) | Note.content.ilike(pattern)
            query = query.where(kw_filter)
            count_query = count_query.where(kw_filter)

        query = query.order_by(Note.updated_at.desc()).limit(limit)

        result = await self.db.execute(query)
        notes = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return notes, total

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

    async def get_active_notes_by_ids(
        self, note_ids: list[uuid.UUID], user_id: uuid.UUID
    ) -> list[Note]:
        """Batch lookup for active (non-deleted) notes."""
        if not note_ids:
            return []
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(
                Note.id.in_(note_ids),
                Note.user_id == user_id,
                Note.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())
