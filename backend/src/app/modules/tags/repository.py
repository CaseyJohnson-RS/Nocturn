import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.tags.models import Tag


class TagsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tag(self, user_id: uuid.UUID, name: str) -> Tag:
        tag = Tag(user_id=user_id, name=name)
        self.db.add(tag)
        await self.db.flush()
        return tag

    async def get_tag_by_id(self, tag_id: uuid.UUID, user_id: uuid.UUID) -> Tag | None:
        result = await self.db.execute(
            select(Tag).where(Tag.id == tag_id, Tag.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_tag_by_name(self, user_id: uuid.UUID, name: str) -> Tag | None:
        result = await self.db.execute(
            select(Tag).where(
                Tag.user_id == user_id,
                func.lower(Tag.name) == name.lower(),
            )
        )
        return result.scalar_one_or_none()

    async def list_tags(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> tuple[list[Tag], int]:
        query = select(Tag).where(Tag.user_id == user_id)
        count_query = select(func.count(Tag.id)).where(Tag.user_id == user_id)

        if search:
            pattern = f"%{search}%"
            query = query.where(Tag.name.ilike(pattern))
            count_query = count_query.where(Tag.name.ilike(pattern))

        query = query.order_by(Tag.name).limit(limit).offset(offset)

        result = await self.db.execute(query)
        tags = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        return tags, total

    async def update_tag_name(self, tag: Tag, new_name: str) -> Tag:
        tag.name = new_name
        await self.db.flush()
        return tag

    async def delete_tag(self, tag: Tag) -> None:
        await self.db.delete(tag)
        await self.db.flush()

    async def get_tags_by_names(
        self, user_id: uuid.UUID, names: list[str],
    ) -> list[Tag]:
        """Batch lookup of tags by name (case-insensitive)."""
        if not names:
            return []
        lower_names = [n.lower() for n in names]
        result = await self.db.execute(
            select(Tag).where(
                Tag.user_id == user_id,
                func.lower(Tag.name).in_(lower_names),
            )
        )
        return list(result.scalars().all())

    async def count_user_tags(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count(Tag.id)).where(Tag.user_id == user_id)
        )
        return result.scalar_one()

    async def verify_tags_belong_to_user(
        self, user_id: uuid.UUID, tag_ids: list[uuid.UUID]
    ) -> list[Tag]:
        if not tag_ids:
            return []
        result = await self.db.execute(
            select(Tag).where(Tag.id.in_(tag_ids), Tag.user_id == user_id)
        )
        return list(result.scalars().all())
