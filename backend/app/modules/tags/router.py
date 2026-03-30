import uuid

from fastapi import APIRouter, Query, status

from app.common.dependencies import DBSession
from app.middleware.auth import AuthUser
from app.modules.tags.schemas import (
    CreateTagRequest,
    TagListResponse,
    TagResponse,
    UpdateTagRequest,
)
from app.modules.tags.service import TagsService

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(body: CreateTagRequest, user: AuthUser, db: DBSession):
    service = TagsService(db)
    return await service.create(user.id, body.name)


@router.get("", response_model=TagListResponse)
async def list_tags(
    user: AuthUser,
    db: DBSession,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=50),
):
    service = TagsService(db)
    return await service.list(user.id, limit, offset, search)


@router.get("/{tag_id}", response_model=TagResponse)
async def get_tag(tag_id: uuid.UUID, user: AuthUser, db: DBSession):
    service = TagsService(db)
    return await service.get(user.id, tag_id)


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(tag_id: uuid.UUID, body: UpdateTagRequest, user: AuthUser, db: DBSession):
    service = TagsService(db)
    return await service.update(user.id, tag_id, body.name)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: uuid.UUID, user: AuthUser, db: DBSession):
    service = TagsService(db)
    await service.delete(user.id, tag_id)
