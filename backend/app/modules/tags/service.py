import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ConflictError, NotFoundError, ValidationError
from app.config import settings
from app.modules.tags.repository import TagsRepository
from app.modules.tags.schemas import TagListResponse, TagResponse

TAG_NAME_PATTERN = re.compile(r"^[\w\sа-яА-ЯёЁ\-]+$", re.UNICODE)


def validate_tag_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValidationError("Tag name cannot be empty")
    if len(name) > 50:
        raise ValidationError("Tag name must be at most 50 characters")
    if not TAG_NAME_PATTERN.match(name):
        raise ValidationError("Tag name contains invalid characters")
    return name


class TagsService:
    def __init__(self, db: AsyncSession):
        self.repo = TagsRepository(db)

    async def create(self, user_id: uuid.UUID, name: str) -> TagResponse:
        name = validate_tag_name(name)

        count = await self.repo.count_user_tags(user_id)
        if count >= settings.max_tags_per_user:
            raise ConflictError("Tag limit reached")

        existing = await self.repo.get_tag_by_name(user_id, name)
        if existing:
            raise ConflictError("Tag with this name already exists")

        tag = await self.repo.create_tag(user_id, name)
        return TagResponse.model_validate(tag)

    async def get(self, user_id: uuid.UUID, tag_id: uuid.UUID) -> TagResponse:
        tag = await self.repo.get_tag_by_id(tag_id, user_id)
        if not tag:
            raise NotFoundError("Tag not found")
        return TagResponse.model_validate(tag)

    async def list(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
    ) -> TagListResponse:
        tags, total = await self.repo.list_tags(user_id, limit, offset, search)
        return TagListResponse(
            items=[TagResponse.model_validate(t) for t in tags],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def update(self, user_id: uuid.UUID, tag_id: uuid.UUID, name: str) -> TagResponse:
        name = validate_tag_name(name)

        tag = await self.repo.get_tag_by_id(tag_id, user_id)
        if not tag:
            raise NotFoundError("Tag not found")

        existing = await self.repo.get_tag_by_name(user_id, name)
        if existing and existing.id != tag_id:
            raise ConflictError("Tag with this name already exists")

        tag = await self.repo.update_tag_name(tag, name)
        return TagResponse.model_validate(tag)

    async def delete(self, user_id: uuid.UUID, tag_id: uuid.UUID) -> None:
        tag = await self.repo.get_tag_by_id(tag_id, user_id)
        if not tag:
            raise NotFoundError("Tag not found")
        await self.repo.delete_tag(tag)
