import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.app.common.dependencies import DBSession
from src.app.middleware.auth import AuthUser
from src.app.modules.tags.schemas import (
    CreateTagRequest,
    TagListResponse,
    TagResponse,
    UpdateTagRequest,
)
from src.app.modules.tags.service import TagsService

router = APIRouter(prefix="/api/tags", tags=["tags"])


async def get_tags_service(db: DBSession) -> TagsService:
    return TagsService(db)


TagsServiceDep = Annotated[TagsService, Depends(get_tags_service)]


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tag",
    responses={409: {"description": "Tag with this name already exists"}},
)
async def create_tag(body: CreateTagRequest, user: AuthUser, service: TagsServiceDep):
    """Create a new tag for the current user.

    Tag names are unique per user (case-insensitive).
    Tags can later be attached to notes via `PUT /api/notes/{note_id}/tags`.
    """
    return await service.create(user.id, body.name)


@router.get(
    "",
    response_model=TagListResponse,
    summary="List tags",
)
async def list_tags(
    user: AuthUser,
    service: TagsServiceDep,
    limit: int = Query(default=100, ge=1, le=100, description="Max number of tags to return"),
    offset: int = Query(default=0, ge=0, description="Number of tags to skip"),
    search: str | None = Query(
        default=None, max_length=50, description="Filter tags by name substring"
    ),
):
    """Return a paginated list of the user's tags.

    Supports optional substring search by tag name.
    Results are sorted alphabetically.
    """
    return await service.list(user.id, limit, offset, search)


@router.get(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Get a tag",
    responses={404: {"description": "Tag not found or does not belong to user"}},
)
async def get_tag(tag_id: uuid.UUID, user: AuthUser, service: TagsServiceDep):
    """Return a single tag by ID."""
    return await service.get(user.id, tag_id)


@router.put(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Rename a tag",
    responses={
        404: {"description": "Tag not found"},
        409: {"description": "Another tag with this name already exists"},
    },
)
async def update_tag(
    tag_id: uuid.UUID, body: UpdateTagRequest, user: AuthUser, service: TagsServiceDep
):
    """Change the name of an existing tag.

    The new name must be unique among the user's tags.
    All notes linked to this tag keep the association.
    """
    return await service.update(user.id, tag_id, body.name)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a tag",
    responses={404: {"description": "Tag not found"}},
)
async def delete_tag(tag_id: uuid.UUID, user: AuthUser, service: TagsServiceDep):
    """Delete a tag and remove it from all associated notes.

    This is a permanent operation — there is no trash/restore for tags.
    """
    await service.delete(user.id, tag_id)
